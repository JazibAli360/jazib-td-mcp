// jzb_vision_bridge -- jazib-td-mcp's copy of td-port's camera_bridge/src/jzb_camera_bridge.mm (sha1 d1f3df8f9940,
// copied 2026-10-26; td-port is a separate project and is never edited from here). Added in this copy: request
// kind 5 = face LANDMARKS (VNDetectFaceLandmarksRequest revision 3, constellation 76) for the face_track COMP
// (builders/face_track.py). Answer: float32, w = 9 + 2 * points, h = faces; per face x y w h (boundingBox, upright
// picture, origin bottom-left), roll yaw pitch (radians, NaN when Vision gives none), face confidence, landmarks
// confidence, then every landmark point (x, y) in IMAGE space (normalized 0..1, origin bottom-left), regions in the
// order of the answer's text = JSON {"regions":[[name,count],...]}; a region a face lacks is NaN.
// Everything below this block is the td-port header, kept as provenance.
//
// jzb_camera_bridge -- td-port's camera-model helper PROCESS for the TouchDesigner ports of JZBV_DepthFX and
// JZBV_PersonKey. TD 2 (2025.31550) is an Intel build under Rosetta; this helper is a separate native arm64 process, so
// Core ML / Vision run natively (and may use the Neural Engine) whatever TD's architecture. TD talks to it over a local
// Unix-domain socket (camera_bridge/README.md "Protocol"; Python side: lib/camera_bridge.py).
//
// The model requests are COPIED from stagelab (read only, HEAD ad2c5bb, 2026-10-14):
//   ffgl/common/DepthWorker.mm (sha1 6441cc5d09cb, last change 1adf506): Core ML Depth Anything V2 Small via
//     VNCoreMLRequest, ScaleFill, CPU + Neural Engine, bottom-up input -> DownMirrored orientation, F16/F32 output ->
//     float rows in GL order (row 0 = bottom of the upright picture). Larger value = nearer.
//   ffgl/common/SegWorker.mm (sha1 7120b7b27e90, last change ee667ba): VNGeneratePersonSegmentationRequest Fast /
//     Balanced, OneComponent8, a FRESH request per frame (a reused one held a stale mask), optional
//     VNGeneratePersonInstanceMaskRequest (macOS 14+), warm-up of both qualities on a grey 128x96 frame.
//   ffgl/common/VisionWorker.mm (sha1 5f1cb966c150, stagelab d67b0c4, unchanged since ad2c5bb; added 2026-10-15 for
//     JZBV_Tracker, spec tracker/BRIDGE_REQUEST.md): VNDetectFaceRectanglesRequest revision 3 on an 8-bit LUMA buffer
//     (Rec. 709 of the BGRA input, as the source feeds Vision), a fresh request per frame, warm-up on a grey 64x64
//     frame. Answer: float32 w = 6, h = faces, per face x, y, w, h (boundingBox: upright picture, origin bottom-left),
//     roll (radians, 0 when nil), confidence. Faces need no model file, so they are on unless --no-faces.
// What changed for a process: the plugin's GCD worker + Submit/Take becomes a poll() event loop; one request at a time
// per client (the client keeps at most one in flight); if a client sends several, only the NEWEST is run and the older
// ones are answered "dropped" (newest-frame policy, bounded memory). Model load / warm-up run on a background queue so
// requests during load get "not ready" at once instead of waiting.
//
// Build: camera_bridge/build.sh (clang++, arm64 only -- see README "Why arm64 only").
// Modes:
//   jzb_camera_bridge info                         JSON: arch, Rosetta, macOS, model path
//   jzb_camera_bridge serve --socket P [--model M] [--no-depth] [--no-seg] [--no-faces] [--parent-pid N] [--idle-exit S]
//                           [--compute ane|cpu|all]
//   jzb_camera_bridge oneshot --kind depth|seg-fast|seg-balanced|faces --in IMG --out PNG [--model M] [--raw F] [--repeat N]
//     (faces: --out is not written; prints the boxes for bottom-up AND top-down rows of the same frame)
#import <CoreGraphics/CoreGraphics.h>
#import <CoreML/CoreML.h>
#import <CoreVideo/CoreVideo.h>
#import <Foundation/Foundation.h>
#import <ImageIO/ImageIO.h>
#import <UniformTypeIdentifiers/UniformTypeIdentifiers.h>
#import <Vision/Vision.h>
#include <errno.h>
#include <fcntl.h>
#include <mach-o/dyld.h>
#include <poll.h>
#include <signal.h>
#include <sys/socket.h>
#include <sys/stat.h>
#include <sys/sysctl.h>
#include <sys/un.h>
#include <unistd.h>
#include <algorithm>
#include <atomic>
#include <chrono>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <mutex>
#include <string>
#include <thread>
#include <vector>
#include "DepthLogic.h"

namespace
{
// ---------------------------------------------------------------- protocol (keep in step with lib/camera_bridge.py)
const std::uint16_t VERSION = 1;
enum Kind : std::uint8_t { KIND_DEPTH = 1, KIND_SEG_FAST = 2, KIND_SEG_BALANCED = 3, KIND_FACES = 4, KIND_LANDMARKS = 5, KIND_INFO = 9 };
enum Status : std::uint8_t { ST_OK = 0, ST_ERROR = 1, ST_NOT_READY = 2, ST_DROPPED = 3, ST_BAD_REQUEST = 4 };
enum Flags : std::uint8_t { FL_BOTTOM_UP = 1, FL_INSTANCES = 2 };
enum Fmt : std::uint8_t { FMT_NONE = 0, FMT_F32 = 1, FMT_U8 = 2 };
const std::size_t REQ_SIZE = 48, RESP_SIZE = 72;
const std::uint32_t MAX_SIDE = 2048;             // bounded input: <= 2048 x 2048 BGRA (16 MB) per request
const std::uint32_t MAX_DELAY_MS = 5000;
const int MAX_CLIENTS = 8;

#pragma pack( push, 1 )
struct Request
{
	char magic[ 4 ];// "JZBQ"
	std::uint16_t version;
	std::uint8_t kind, flags;
	std::uint64_t frameId;
	double stamp;
	std::uint32_t width, height, delayMs, payloadLen, reserved0, reserved1;
};
struct Response
{
	char magic[ 4 ];// "JZBR"
	std::uint16_t version;
	std::uint8_t kind, status;
	std::uint64_t frameId;
	double stamp;
	std::uint32_t outW, outH;
	std::uint8_t outFmt, pad[ 3 ];
	float computeMs, waitMs, pLo, pHi;
	std::uint32_t instW, instH, payloadLen, instLen, textLen;
};
#pragma pack( pop )
static_assert( sizeof( Request ) == REQ_SIZE, "request header size" );
static_assert( sizeof( Response ) == RESP_SIZE, "response header size" );

double NowMs() { return std::chrono::duration< double, std::milli >( std::chrono::steady_clock::now().time_since_epoch() ).count(); }

std::string JsonEscape( const std::string& s )
{
	std::string o;
	for( char c : s )
	{
		if( c == '"' || c == '\\' ) { o += '\\'; o += c; }
		else if( (unsigned char)c < 0x20 ) o += ' ';
		else o += c;
	}
	return o;
}

bool Translated()
{
	int t = 0;
	size_t n = sizeof t;
	return sysctlbyname( "sysctl.proc_translated", &t, &n, nullptr, 0 ) == 0 && t == 1;
}

const char* Arch()
{
#if defined( __arm64__ ) || defined( __aarch64__ )
	return "arm64";
#elif defined( __x86_64__ )
	return "x86_64";
#else
	return "unknown";
#endif
}

std::string ExeDir()
{
	char buf[ 4096 ];
	uint32_t n = sizeof buf;
	if( _NSGetExecutablePath( buf, &n ) != 0 ) return ".";
	std::string p = buf;
	const std::size_t k = p.rfind( '/' );
	return k == std::string::npos ? "." : p.substr( 0, k );
}

// build/jzb_vision_bridge -> ../assets/<model> (copied 26 Oct for depth_cam, git-ignored, assets/LICENSE-NOTICE.txt;
// face_track still runs with --no-depth so it never loads the 50 MB model)
std::string DefaultModelPath() { return ExeDir() + "/../assets/DepthAnythingV2SmallF16.mlmodelc"; }

// ---------------------------------------------------------------- the models (copied request code, see header)
struct Engine
{
	std::string modelPath;
	MLComputeUnits units = MLComputeUnitsCPUAndNeuralEngine;// DepthWorker: keep the GPU free for the host
	bool wantDepth = true, wantSeg = true, wantFaces = true, wantLandmarks = true;
	std::atomic< bool > depthReady{ false }, depthFailed{ false }, segReady{ false }, facesReady{ false }, landmarksReady{ false };
	std::mutex lock;
	std::string depthError, segError, facesError, landmarksError;
	double depthLoadMs = 0.0, segWarmMs = 0.0, facesWarmMs = 0.0, landmarksWarmMs = 0.0;
	VNCoreMLModel* model = nil;// written once on the load queue before depthReady

	void StartLoading( bool block )
	{
		dispatch_queue_t q = dispatch_queue_create( "jazib-td-mcp.vision_bridge.load", DISPATCH_QUEUE_SERIAL );
		if( wantDepth )
			dispatch_async( q, ^{ LoadDepth(); } );
		if( wantSeg )
			dispatch_async( q, ^{ WarmSeg(); } );
		if( wantFaces )
			dispatch_async( q, ^{ WarmFaces(); } );
		if( wantLandmarks )
			dispatch_async( q, ^{ WarmLandmarks(); } );
		if( block ) dispatch_sync( q, ^{} );
	}

	void LoadDepth()
	{
		const double t0 = NowMs();
		@autoreleasepool
		{
			NSError* err = nil;
			MLModelConfiguration* cfg = [[MLModelConfiguration alloc] init];
			cfg.computeUnits = units;
			MLModel* ml = [MLModel modelWithContentsOfURL:[NSURL fileURLWithPath:@( modelPath.c_str() )] configuration:cfg error:&err];
			VNCoreMLModel* vn = ml ? [VNCoreMLModel modelForMLModel:ml error:&err] : nil;
			std::lock_guard< std::mutex > g( lock );
			depthLoadMs = NowMs() - t0;
			if( !vn )
			{
				depthError = std::string( "model load failed: " ) + ( err ? err.localizedDescription.UTF8String : modelPath.c_str() );
				depthFailed = true;
				return;
			}
			model = vn;
		}
		depthReady = true;
	}

	static VNGeneratePersonSegmentationRequest* MakeSeg( VNGeneratePersonSegmentationRequestQualityLevel q )
	{
		VNGeneratePersonSegmentationRequest* r = [[VNGeneratePersonSegmentationRequest alloc] init];
		r.qualityLevel = q;
		r.outputPixelFormat = kCVPixelFormatType_OneComponent8;
		return r;
	}

	void WarmSeg()
	{
		const double t0 = NowMs();
		std::string error;
		@autoreleasepool
		{
			CVPixelBufferRef pb = nullptr;
			if( CVPixelBufferCreate( kCFAllocatorDefault, 128, 96, kCVPixelFormatType_32BGRA, nullptr, &pb ) == kCVReturnSuccess )
			{
				CVPixelBufferLockBaseAddress( pb, 0 );
				std::memset( CVPixelBufferGetBaseAddress( pb ), 128, CVPixelBufferGetBytesPerRow( pb ) * 96 );
				CVPixelBufferUnlockBaseAddress( pb, 0 );
				VNImageRequestHandler* handler = [[VNImageRequestHandler alloc] initWithCVPixelBuffer:pb options:@{}];
				NSError* err = nil;
				if( ![handler performRequests:@[ MakeSeg( VNGeneratePersonSegmentationRequestQualityLevelFast ),
				                                   MakeSeg( VNGeneratePersonSegmentationRequestQualityLevelBalanced ) ] error:&err] )
					error = err ? err.localizedDescription.UTF8String : "warm-up failed";
				CVPixelBufferRelease( pb );
			}
			else error = "warm-up buffer failed";
		}
		std::lock_guard< std::mutex > g( lock );
		segWarmMs = NowMs() - t0;
		segError = error;
		segReady = true;// as in SegWorker: a failed warm-up still lets real requests try (and report their own error)
	}

	static CVPixelBufferRef Wrap( const std::uint8_t* bgra, int w, int h )
	{
		CVPixelBufferRef pb = nullptr;
		if( CVPixelBufferCreate( kCFAllocatorDefault, (size_t)w, (size_t)h, kCVPixelFormatType_32BGRA, nullptr, &pb ) != kCVReturnSuccess ) return nullptr;
		CVPixelBufferLockBaseAddress( pb, 0 );
		auto* dst = (std::uint8_t*)CVPixelBufferGetBaseAddress( pb );
		const size_t dstRow = CVPixelBufferGetBytesPerRow( pb );
		for( int y = 0; y < h; ++y ) std::memcpy( dst + (size_t)y * dstRow, bgra + (size_t)y * w * 4, (size_t)w * 4 );
		CVPixelBufferUnlockBaseAddress( pb, 0 );
		return pb;
	}

	// DepthWorker::Submit's block, synchronous. out: ow x oh floats, GL row order.
	std::string Depth( const std::uint8_t* bgra, int w, int h, bool bottomUp, std::vector< float >& out, int& ow, int& oh, double& ms )
	{
		CVPixelBufferRef pb = Wrap( bgra, w, h );
		if( !pb ) return "pixel buffer failed";
		const CGImagePropertyOrientation orientation = bottomUp ? kCGImagePropertyOrientationDownMirrored : kCGImagePropertyOrientationUp;
		const double t0 = NowMs();
		std::string error;
		@autoreleasepool
		{
			VNCoreMLRequest* req = [[VNCoreMLRequest alloc] initWithModel:model];
			req.imageCropAndScaleOption = VNImageCropAndScaleOptionScaleFill;
			VNImageRequestHandler* handler = [[VNImageRequestHandler alloc] initWithCVPixelBuffer:pb orientation:orientation options:@{}];
			NSError* err = nil;
			if( ![handler performRequests:@[ req ] error:&err] ) error = err ? err.localizedDescription.UTF8String : "depth request failed";
			else if( VNPixelBufferObservation* o = (VNPixelBufferObservation*)req.results.firstObject; [o isKindOfClass:[VNPixelBufferObservation class]] )
			{
				CVPixelBufferRef d = o.pixelBuffer;
				const OSType fmt = CVPixelBufferGetPixelFormatType( d );
				CVPixelBufferLockBaseAddress( d, kCVPixelBufferLock_ReadOnly );
				ow = (int)CVPixelBufferGetWidth( d );
				oh = (int)CVPixelBufferGetHeight( d );
				const size_t rb = CVPixelBufferGetBytesPerRow( d );
				const auto* base = (const std::uint8_t*)CVPixelBufferGetBaseAddress( d );
				out.resize( (size_t)ow * oh );
				for( int y = 0; y < oh; ++y )// buffer row 0 = top of the upright picture -> GL order (row 0 = bottom)
				{
					float* row = &out[ (size_t)( oh - 1 - y ) * ow ];
					if( fmt == kCVPixelFormatType_OneComponent16Half )
					{
						const __fp16* src = (const __fp16*)( base + (size_t)y * rb );
						for( int x = 0; x < ow; ++x ) row[ x ] = (float)src[ x ];
					}
					else if( fmt == kCVPixelFormatType_OneComponent32Float )
						std::memcpy( row, base + (size_t)y * rb, (size_t)ow * 4 );
					else { error = "unexpected depth pixel format"; break; }
				}
				CVPixelBufferUnlockBaseAddress( d, kCVPixelBufferLock_ReadOnly );
			}
			else error = "no depth in the result";
		}
		ms = NowMs() - t0;
		CVPixelBufferRelease( pb );
		return error;
	}

	static bool CopyR8( CVPixelBufferRef b, std::vector< std::uint8_t >& out, int& w, int& h )
	{
		if( !b || CVPixelBufferGetPixelFormatType( b ) != kCVPixelFormatType_OneComponent8 ) return false;
		CVPixelBufferLockBaseAddress( b, kCVPixelBufferLock_ReadOnly );
		w = (int)CVPixelBufferGetWidth( b );
		h = (int)CVPixelBufferGetHeight( b );
		const size_t rb = CVPixelBufferGetBytesPerRow( b );
		const auto* base = (const std::uint8_t*)CVPixelBufferGetBaseAddress( b );
		out.resize( (size_t)w * h );
		for( int y = 0; y < h; ++y ) std::memcpy( &out[ (size_t)( h - 1 - y ) * w ], base + (size_t)y * rb, (size_t)w );
		CVPixelBufferUnlockBaseAddress( b, kCVPixelBufferLock_ReadOnly );
		return true;
	}

	// SegWorker::Submit's block, synchronous. mask / inst: GL row order.
	std::string Seg( const std::uint8_t* bgra, int w, int h, bool bottomUp, bool balanced, bool instances, std::vector< std::uint8_t >& mask,
	                 int& mw, int& mh, std::vector< std::uint8_t >& inst, int& iw, int& ih, double& ms )
	{
		CVPixelBufferRef pb = Wrap( bgra, w, h );
		if( !pb ) return "pixel buffer failed";
		const CGImagePropertyOrientation orientation = bottomUp ? kCGImagePropertyOrientationDownMirrored : kCGImagePropertyOrientationUp;
		const double t0 = NowMs();
		std::string error;
		iw = ih = 0;
		inst.clear();
		@autoreleasepool
		{
			VNGeneratePersonSegmentationRequest* seg = MakeSeg( balanced ? VNGeneratePersonSegmentationRequestQualityLevelBalanced
			                                                             : VNGeneratePersonSegmentationRequestQualityLevelFast );
			NSMutableArray< VNRequest* >* reqs = [NSMutableArray arrayWithObject:seg];
			VNRequest* instReq = nil;
			if( instances )
			{
				if( @available( macOS 14.0, * ) )
				{
					instReq = [[VNGeneratePersonInstanceMaskRequest alloc] init];
					[reqs addObject:instReq];
				}
			}
			VNImageRequestHandler* handler = [[VNImageRequestHandler alloc] initWithCVPixelBuffer:pb orientation:orientation options:@{}];
			NSError* err = nil;
			if( ![handler performRequests:reqs error:&err] ) error = err ? err.localizedDescription.UTF8String : "segmentation request failed";
			else
			{
				VNPixelBufferObservation* o = seg.results.firstObject;
				if( !o || !CopyR8( o.pixelBuffer, mask, mw, mh ) ) error = "no person mask in the result";
				if( instReq )
				{
					if( @available( macOS 14.0, * ) )
					{
						VNInstanceMaskObservation* io = (VNInstanceMaskObservation*)instReq.results.firstObject;
						if( io ) CopyR8( io.instanceMask, inst, iw, ih );
					}
				}
			}
		}
		ms = NowMs() - t0;
		CVPixelBufferRelease( pb );
		return error;
	}

	// VisionWorker.mm MakeLuma: an 8-bit one-component buffer. Here from BGRA8 rows (Rec. 709 luma, rounded).
	static CVPixelBufferRef MakeLuma( const std::uint8_t* bgra, int w, int h )
	{
		CVPixelBufferRef pb = nullptr;
		if( CVPixelBufferCreate( kCFAllocatorDefault, (size_t)w, (size_t)h, kCVPixelFormatType_OneComponent8, nullptr, &pb ) != kCVReturnSuccess ) return nullptr;
		CVPixelBufferLockBaseAddress( pb, 0 );
		auto* dst = (std::uint8_t*)CVPixelBufferGetBaseAddress( pb );
		const size_t dstRow = CVPixelBufferGetBytesPerRow( pb );
		for( int y = 0; y < h; ++y )
		{
			const std::uint8_t* s = bgra + (size_t)y * w * 4;
			std::uint8_t* d = dst + (size_t)y * dstRow;
			for( int x = 0; x < w; ++x, s += 4 )
				d[ x ] = (std::uint8_t)std::min( 255.0f, 0.0722f * s[ 0 ] + 0.7152f * s[ 1 ] + 0.2126f * s[ 2 ] + 0.5f );
		}
		CVPixelBufferUnlockBaseAddress( pb, 0 );
		return pb;
	}

	// VisionWorker.mm Detect(), copied: 6 floats per face, x y w h roll confidence.
	static std::string DetectFaces( CVPixelBufferRef pb, CGImagePropertyOrientation orientation, std::vector< float >& out )
	{
		out.clear();
		std::string error;
		@autoreleasepool
		{
			VNDetectFaceRectanglesRequest* req = [[VNDetectFaceRectanglesRequest alloc] init];
			req.revision = VNDetectFaceRectanglesRequestRevision3;
			VNImageRequestHandler* handler = [[VNImageRequestHandler alloc] initWithCVPixelBuffer:pb orientation:orientation options:@{}];
			NSError* err = nil;
			if( ![handler performRequests:@[ req ] error:&err] ) return err ? err.localizedDescription.UTF8String : "Vision request failed";
			for( VNFaceObservation* o in req.results )
			{
				const CGRect b = o.boundingBox;
				out.insert( out.end(), { (float)b.origin.x, (float)b.origin.y, (float)b.size.width, (float)b.size.height,
				                         o.roll ? o.roll.floatValue : 0.f, o.confidence } );
			}
		}
		return error;
	}

	void WarmFaces()
	{
		const double t0 = NowMs();
		std::string error;
		std::vector< std::uint8_t > grey( 64 * 64 * 4, 128 );
		if( CVPixelBufferRef pb = MakeLuma( grey.data(), 64, 64 ) )
		{
			std::vector< float > none;
			error = DetectFaces( pb, kCGImagePropertyOrientationUp, none );
			CVPixelBufferRelease( pb );
		}
		else error = "warm-up buffer failed";
		std::lock_guard< std::mutex > g( lock );
		facesWarmMs = NowMs() - t0;
		facesError = error;
		facesReady = true;// as VisionWorker: ready after the warm-up whatever it reported
	}

	std::string Faces( const std::uint8_t* bgra, int w, int h, bool bottomUp, std::vector< float >& out, double& ms )
	{
		CVPixelBufferRef pb = MakeLuma( bgra, w, h );
		if( !pb ) return "pixel buffer failed";
		const CGImagePropertyOrientation orientation = bottomUp ? kCGImagePropertyOrientationDownMirrored : kCGImagePropertyOrientationUp;
		const double t0 = NowMs();
		const std::string error = DetectFaces( pb, orientation, out );
		ms = NowMs() - t0;
		CVPixelBufferRelease( pb );
		return error;
	}

	// ---- jazib-td-mcp addition: kind 5, face landmarks (see the header block).
	// Fixed region order; names are the face_track channel names (builders/face_track_logic.py REGIONS).
	static NSArray< NSString* >* RegionKeys()
	{
		return @[ @"faceContour", @"leftEyebrow", @"rightEyebrow", @"leftEye", @"rightEye", @"leftPupil", @"rightPupil",
		          @"nose", @"noseCrest", @"medianLine", @"outerLips", @"innerLips" ];
	}
	static const char* RegionName( NSUInteger i )
	{
		static const char* n[] = { "jaw", "brow_l", "brow_r", "eye_l", "eye_r", "pupil_l", "pupil_r", "nose", "nosecrest", "median",
		                           "lips_outer", "lips_inner" };
		return n[ i ];
	}

	// out: rows of 9 + 2 * sum(counts) floats; counts: points per region (from the first face that has the region).
	static std::string DetectLandmarks( CVPixelBufferRef pb, CGImagePropertyOrientation orientation, std::vector< float >& out,
	                                    std::vector< int >& counts )
	{
		out.clear();
		NSArray< NSString* >* keys = RegionKeys();
		counts.assign( keys.count, 0 );
		@autoreleasepool
		{
			// Pass 1: face rectangles revision 3 (finds more partial / cut-off faces than the landmarks request's own
			// detector: 36 vs 24 of 150 frames on media/webcam/webcam_ref_5s.mp4 at 960x540, README). Pass 2: landmarks
			// on those boxes (inputFaceObservations); with no box found, the landmarks request detects on its own.
			VNImageRequestHandler* handler = [[VNImageRequestHandler alloc] initWithCVPixelBuffer:pb orientation:orientation options:@{}];
			NSError* err = nil;
			VNDetectFaceRectanglesRequest* rects = [[VNDetectFaceRectanglesRequest alloc] init];
			rects.revision = VNDetectFaceRectanglesRequestRevision3;
			if( ![handler performRequests:@[ rects ] error:&err] ) return err ? err.localizedDescription.UTF8String : "Vision face request failed";
			VNDetectFaceLandmarksRequest* req = [[VNDetectFaceLandmarksRequest alloc] init];
			req.revision = VNDetectFaceLandmarksRequestRevision3;
			req.constellation = VNRequestFaceLandmarksConstellation76Points;
			if( rects.results.count )
			{
				// Boxes only: the rectangles' roll on a cut-off face is unreliable (up to -77 deg on an upright face)
				// and the landmarks follow it, so the seed carries no roll / yaw (README "Landmarks").
				NSMutableArray< VNFaceObservation* >* seeds = [NSMutableArray array];
				for( VNFaceObservation* o in rects.results )
					[seeds addObject:[VNFaceObservation faceObservationWithRequestRevision:VNDetectFaceLandmarksRequestRevision3
					                                                           boundingBox:o.boundingBox roll:nil yaw:nil pitch:nil]];
				req.inputFaceObservations = seeds;
			}
			if( ![handler performRequests:@[ req ] error:&err] ) return err ? err.localizedDescription.UTF8String : "Vision landmarks request failed";
			NSArray< VNFaceObservation* >* faces = req.results;
			for( VNFaceObservation* o in faces )
				for( NSUInteger r = 0; r < keys.count; ++r )
				{
					VNFaceLandmarkRegion2D* g = o.landmarks ? [o.landmarks valueForKey:keys[ r ]] : nil;
					if( g && counts[ r ] == 0 ) counts[ r ] = (int)g.pointCount;
				}
			int total = 0;
			for( int c : counts ) total += c;
			const float nan = std::nanf( "" );
			for( VNFaceObservation* o in faces )
			{
				const CGRect b = o.boundingBox;
				// pose: the landmarks' own when present, else the matching rectangle's (nearest box centre)
				VNFaceObservation* pose = o;
				if( !o.roll && !o.yaw )
				{
					double best = 1e9;
					for( VNFaceObservation* q in rects.results )
					{
						const double d = std::hypot( CGRectGetMidX( q.boundingBox ) - CGRectGetMidX( b ), CGRectGetMidY( q.boundingBox ) - CGRectGetMidY( b ) );
						if( d < best ) { best = d; pose = q; }
					}
				}
				float yaw = nan, pitch = nan;
				if( pose.yaw ) yaw = pose.yaw.floatValue;
				if( @available( macOS 12.0, * ) ) { if( pose.pitch ) pitch = pose.pitch.floatValue; }
				out.insert( out.end(), { (float)b.origin.x, (float)b.origin.y, (float)b.size.width, (float)b.size.height,
				                         pose.roll ? pose.roll.floatValue : nan, yaw, pitch, o.confidence,
				                         o.landmarks ? o.landmarks.confidence : nan } );
				for( NSUInteger r = 0; r < keys.count; ++r )
				{
					VNFaceLandmarkRegion2D* g = o.landmarks ? [o.landmarks valueForKey:keys[ r ]] : nil;
					const int n = counts[ r ];
					const int have = g ? (int)g.pointCount : 0;
					const CGPoint* pts = g ? g.normalizedPoints : nullptr;
					for( int k = 0; k < n; ++k )
					{
						if( k < have && pts )// box-relative -> image space (upright picture, origin bottom-left)
							out.insert( out.end(), { (float)( b.origin.x + pts[ k ].x * b.size.width ), (float)( b.origin.y + pts[ k ].y * b.size.height ) } );
						else out.insert( out.end(), { nan, nan } );
					}
				}
			}
			(void)total;
		}
		return std::string();
	}

	static std::string LayoutJson( const std::vector< int >& counts )
	{
		std::string t = "{\"regions\":[";
		for( std::size_t r = 0; r < counts.size(); ++r )
			t += std::string( r ? "," : "" ) + "[\"" + RegionName( r ) + "\"," + std::to_string( counts[ r ] ) + "]";
		return t + "]}";
	}

	void WarmLandmarks()
	{
		const double t0 = NowMs();
		std::string error;
		std::vector< std::uint8_t > grey( 64 * 64 * 4, 128 );
		if( CVPixelBufferRef pb = Wrap( grey.data(), 64, 64 ) )
		{
			std::vector< float > none;
			std::vector< int > counts;
			error = DetectLandmarks( pb, kCGImagePropertyOrientationUp, none, counts );
			CVPixelBufferRelease( pb );
		}
		else error = "warm-up buffer failed";
		std::lock_guard< std::mutex > g( lock );
		landmarksWarmMs = NowMs() - t0;
		landmarksError = error;
		landmarksReady = true;
	}

	std::string Landmarks( const std::uint8_t* bgra, int w, int h, bool bottomUp, std::vector< float >& out, std::vector< int >& counts, double& ms )
	{
		CVPixelBufferRef pb = Wrap( bgra, w, h );
		if( !pb ) return "pixel buffer failed";
		const CGImagePropertyOrientation orientation = bottomUp ? kCGImagePropertyOrientationDownMirrored : kCGImagePropertyOrientationUp;
		const double t0 = NowMs();
		const std::string error = DetectLandmarks( pb, orientation, out, counts );
		ms = NowMs() - t0;
		CVPixelBufferRelease( pb );
		return error;
	}

	std::string InfoJson()
	{
		std::lock_guard< std::mutex > g( lock );
		char buf[ 2048 ];
		std::snprintf( buf, sizeof buf,
		               "{\"helper\":\"jzb_vision_bridge\",\"protocol\":%u,\"arch\":\"%s\",\"translated\":%s,\"macos\":\"%s\",\"pid\":%d,"
		               "\"model\":\"%s\",\"depth_ready\":%s,\"depth_failed\":%s,\"depth_load_ms\":%.1f,\"depth_error\":\"%s\","
		               "\"seg_ready\":%s,\"seg_warm_ms\":%.1f,\"seg_error\":\"%s\",\"faces\":%s,\"faces_ready\":%s,"
		               "\"faces_warm_ms\":%.1f,\"faces_error\":\"%s\",\"landmarks\":%s,\"landmarks_ready\":%s,\"landmarks_warm_ms\":%.1f,"
		               "\"landmarks_error\":\"%s\",\"compute\":\"%s\"}",
		               (unsigned)VERSION, Arch(), Translated() ? "true" : "false",
		               NSProcessInfo.processInfo.operatingSystemVersionString.UTF8String, (int)getpid(), JsonEscape( modelPath ).c_str(),
		               depthReady ? "true" : "false", depthFailed ? "true" : "false", depthLoadMs, JsonEscape( depthError ).c_str(),
		               segReady ? "true" : "false", segWarmMs, JsonEscape( segError ).c_str(),
		               wantFaces ? "true" : "false", facesReady ? "true" : "false", facesWarmMs, JsonEscape( facesError ).c_str(),
		               wantLandmarks ? "true" : "false", landmarksReady ? "true" : "false", landmarksWarmMs, JsonEscape( landmarksError ).c_str(),
		               units == MLComputeUnitsCPUOnly ? "cpu" : units == MLComputeUnitsAll ? "all" : "cpu+ane" );
		return buf;
	}
};

// ---------------------------------------------------------------- server
struct Client
{
	int fd = -1;
	std::vector< std::uint8_t > in, out;
	std::size_t outPos = 0;
	bool closeAfterWrite = false;
};

void AppendResponse( Client& c, const Response& r, const void* payload, const void* inst, const std::string& text )
{
	const std::uint8_t* p = (const std::uint8_t*)&r;
	c.out.insert( c.out.end(), p, p + RESP_SIZE );
	if( r.payloadLen ) c.out.insert( c.out.end(), (const std::uint8_t*)payload, (const std::uint8_t*)payload + r.payloadLen );
	if( r.instLen ) c.out.insert( c.out.end(), (const std::uint8_t*)inst, (const std::uint8_t*)inst + r.instLen );
	if( r.textLen ) c.out.insert( c.out.end(), text.begin(), text.end() );
}

Response Header( const Request& q, Status st )
{
	Response r;
	std::memset( &r, 0, sizeof r );
	std::memcpy( r.magic, "JZBR", 4 );
	r.version = VERSION;
	r.kind = q.kind;
	r.status = st;
	r.frameId = q.frameId;
	r.stamp = q.stamp;
	return r;
}

void Reply( Client& c, const Request& q, Status st, const std::string& text )
{
	Response r = Header( q, st );
	r.textLen = (std::uint32_t)text.size();
	AppendResponse( c, r, nullptr, nullptr, text );
}

// A request header at `p` (`avail` bytes there): its total size once complete, 0 if incomplete, -1 if malformed.
long ParseRequest( const std::uint8_t* p, std::size_t avail, Request& q )
{
	if( avail < REQ_SIZE ) return 0;
	std::memcpy( &q, p, REQ_SIZE );
	if( std::memcmp( q.magic, "JZBQ", 4 ) != 0 || q.version != VERSION ) return -1;
	if( q.kind == KIND_INFO ) { if( q.payloadLen != 0 ) return -1; }
	else
	{
		if( q.width == 0 || q.height == 0 || q.width > MAX_SIDE || q.height > MAX_SIDE ) return -1;
		if( q.payloadLen != q.width * q.height * 4 ) return -1;
	}
	const std::size_t total = REQ_SIZE + q.payloadLen;
	return avail >= total ? (long)total : 0;
}

void Serve( Engine& e, Client& c, const Request& q, const std::uint8_t* px, double receivedMs )
{
	const double startMs = NowMs();
	if( q.kind == KIND_INFO ) { Reply( c, q, ST_OK, e.InfoJson() ); return; }
	if( q.delayMs ) std::this_thread::sleep_for( std::chrono::milliseconds( std::min( q.delayMs, MAX_DELAY_MS ) ) );// test hook
	const bool bottomUp = q.flags & FL_BOTTOM_UP;
	if( q.kind == KIND_DEPTH )
	{
		if( !e.wantDepth ) { Reply( c, q, ST_ERROR, "depth disabled in this helper (--no-depth)" ); return; }
		if( e.depthFailed ) { std::lock_guard< std::mutex > g( e.lock ); Reply( c, q, ST_ERROR, e.depthError ); return; }
		if( !e.depthReady ) { Reply( c, q, ST_NOT_READY, "depth model loading" ); return; }
		std::vector< float > d;
		int ow = 0, oh = 0;
		double ms = 0;
		const std::string err = e.Depth( px, (int)q.width, (int)q.height, bottomUp, d, ow, oh, ms );
		if( !err.empty() ) { Reply( c, q, ST_ERROR, err ); return; }
		const stagelab::DepthRange p = stagelab::Percentiles( d.data(), d.size() );
		Response r = Header( q, ST_OK );
		r.outW = (std::uint32_t)ow; r.outH = (std::uint32_t)oh; r.outFmt = FMT_F32;
		r.computeMs = (float)ms; r.waitMs = (float)( startMs - receivedMs ); r.pLo = p.lo; r.pHi = p.hi;
		r.payloadLen = (std::uint32_t)( d.size() * sizeof( float ) );
		AppendResponse( c, r, d.data(), nullptr, std::string() );
		return;
	}
	if( q.kind == KIND_SEG_FAST || q.kind == KIND_SEG_BALANCED )
	{
		if( !e.wantSeg ) { Reply( c, q, ST_ERROR, "segmentation disabled in this helper (--no-seg)" ); return; }
		if( !e.segReady ) { Reply( c, q, ST_NOT_READY, "segmentation warming up" ); return; }
		std::vector< std::uint8_t > mask, inst;
		int mw = 0, mh = 0, iw = 0, ih = 0;
		double ms = 0;
		const std::string err = e.Seg( px, (int)q.width, (int)q.height, bottomUp, q.kind == KIND_SEG_BALANCED, q.flags & FL_INSTANCES, mask, mw, mh, inst, iw, ih, ms );
		if( !err.empty() ) { Reply( c, q, ST_ERROR, err ); return; }
		Response r = Header( q, ST_OK );
		r.outW = (std::uint32_t)mw; r.outH = (std::uint32_t)mh; r.outFmt = FMT_U8;
		r.computeMs = (float)ms; r.waitMs = (float)( startMs - receivedMs );
		r.instW = (std::uint32_t)iw; r.instH = (std::uint32_t)ih;
		r.payloadLen = (std::uint32_t)mask.size();
		r.instLen = (std::uint32_t)inst.size();
		AppendResponse( c, r, mask.data(), inst.data(), std::string() );
		return;
	}
	if( q.kind == KIND_FACES )
	{
		if( !e.wantFaces ) { Reply( c, q, ST_ERROR, "faces disabled in this helper (--no-faces)" ); return; }
		if( !e.facesReady ) { Reply( c, q, ST_NOT_READY, "face detection warming up" ); return; }
		std::vector< float > f;
		double ms = 0;
		const std::string err = e.Faces( px, (int)q.width, (int)q.height, bottomUp, f, ms );
		if( !err.empty() ) { Reply( c, q, ST_ERROR, err ); return; }
		Response r = Header( q, ST_OK );
		r.outW = 6; r.outH = (std::uint32_t)( f.size() / 6 ); r.outFmt = FMT_F32;
		r.computeMs = (float)ms; r.waitMs = (float)( startMs - receivedMs );
		r.payloadLen = (std::uint32_t)( f.size() * sizeof( float ) );
		AppendResponse( c, r, f.data(), nullptr, std::string() );
		return;
	}
	if( q.kind == KIND_LANDMARKS )
	{
		if( !e.wantLandmarks ) { Reply( c, q, ST_ERROR, "landmarks disabled in this helper (--no-landmarks)" ); return; }
		if( !e.landmarksReady ) { Reply( c, q, ST_NOT_READY, "face landmarks warming up" ); return; }
		std::vector< float > f;
		std::vector< int > counts;
		double ms = 0;
		const std::string err = e.Landmarks( px, (int)q.width, (int)q.height, bottomUp, f, counts, ms );
		if( !err.empty() ) { Reply( c, q, ST_ERROR, err ); return; }
		int total = 0;
		for( int n : counts ) total += n;
		const std::string layout = Engine::LayoutJson( counts );
		Response r = Header( q, ST_OK );
		r.outW = (std::uint32_t)( 9 + 2 * total ); r.outH = (std::uint32_t)( f.size() / ( 9 + 2 * total ) ); r.outFmt = FMT_F32;
		r.computeMs = (float)ms; r.waitMs = (float)( startMs - receivedMs );
		r.payloadLen = (std::uint32_t)( f.size() * sizeof( float ) );
		r.textLen = (std::uint32_t)layout.size();
		AppendResponse( c, r, f.data(), nullptr, layout );
		return;
	}
	Reply( c, q, ST_BAD_REQUEST, "unknown kind" );
}

volatile sig_atomic_t gStop = 0;
void OnSignal( int ) { gStop = 1; }

bool SocketAlive( const std::string& path )
{
	const int fd = socket( AF_UNIX, SOCK_STREAM, 0 );
	if( fd < 0 ) return false;
	sockaddr_un a;
	std::memset( &a, 0, sizeof a );
	a.sun_family = AF_UNIX;
	std::strncpy( a.sun_path, path.c_str(), sizeof a.sun_path - 1 );
	const bool ok = connect( fd, (sockaddr*)&a, sizeof a ) == 0;
	close( fd );
	return ok;
}

void SetNonBlocking( int fd ) { fcntl( fd, F_SETFL, fcntl( fd, F_GETFL ) | O_NONBLOCK ); }

int RunServer( Engine& e, const std::string& path, int parentPid, double idleExitS )
{
	if( path.size() >= sizeof( sockaddr_un::sun_path ) ) { std::fprintf( stderr, "socket path too long (%zu)\n", path.size() ); return 2; }
	if( SocketAlive( path ) ) { std::fprintf( stderr, "another helper is serving %s\n", path.c_str() ); return 3; }
	unlink( path.c_str() );
	const int lfd = socket( AF_UNIX, SOCK_STREAM, 0 );
	sockaddr_un a;
	std::memset( &a, 0, sizeof a );
	a.sun_family = AF_UNIX;
	std::strncpy( a.sun_path, path.c_str(), sizeof a.sun_path - 1 );
	const mode_t old = umask( 077 );// socket file: this user only
	const int b = bind( lfd, (sockaddr*)&a, sizeof a );
	umask( old );
	if( b != 0 || listen( lfd, 4 ) != 0 ) { std::fprintf( stderr, "bind/listen %s: %s\n", path.c_str(), std::strerror( errno ) ); return 2; }
	SetNonBlocking( lfd );
	signal( SIGPIPE, SIG_IGN );
	signal( SIGTERM, OnSignal );
	signal( SIGINT, OnSignal );
	e.StartLoading( false );
	std::printf( "%s\n", e.InfoJson().c_str() );
	std::printf( "serving %s\n", path.c_str() );
	std::fflush( stdout );

	std::vector< Client > clients;
	double idleSince = NowMs();
	std::size_t next = 0;// round robin
	while( !gStop )
	{
		if( parentPid > 0 && ( getppid() != parentPid || kill( parentPid, 0 ) != 0 ) ) { std::printf( "parent %d gone, exiting\n", parentPid ); break; }
		if( clients.empty() && idleExitS > 0 && NowMs() - idleSince > idleExitS * 1000.0 ) { std::printf( "idle %.0f s, exiting\n", idleExitS ); break; }
		std::vector< pollfd > fds;
		fds.push_back( { lfd, POLLIN, 0 } );
		for( Client& c : clients ) fds.push_back( { c.fd, (short)( POLLIN | ( c.outPos < c.out.size() ? POLLOUT : 0 ) ), 0 } );
		if( poll( fds.data(), (nfds_t)fds.size(), 200 ) < 0 && errno != EINTR ) break;
		if( fds[ 0 ].revents & POLLIN )
		{
			for( ;; )
			{
				const int cfd = accept( lfd, nullptr, nullptr );
				if( cfd < 0 ) break;
				if( (int)clients.size() >= MAX_CLIENTS ) { close( cfd ); continue; }
				SetNonBlocking( cfd );
				int big = 4 << 20;
				setsockopt( cfd, SOL_SOCKET, SO_SNDBUF, &big, sizeof big );
				setsockopt( cfd, SOL_SOCKET, SO_RCVBUF, &big, sizeof big );
				Client c;
				c.fd = cfd;
				clients.push_back( std::move( c ) );
			}
		}
		// I/O for every client; collect complete requests.
		for( std::size_t i = 0; i < clients.size(); ++i )
		{
			Client& c = clients[ i ];
			bool dead = false;
			for( ;; )
			{
				std::uint8_t buf[ 1 << 16 ];
				const ssize_t n = read( c.fd, buf, sizeof buf );
				if( n > 0 ) { c.in.insert( c.in.end(), buf, buf + n ); if( c.in.size() > REQ_SIZE + 4ull * MAX_SIDE * MAX_SIDE * 2 ) { dead = true; break; } continue; }
				if( n == 0 ) dead = true;
				else if( errno != EAGAIN && errno != EWOULDBLOCK && errno != EINTR ) dead = true;
				break;
			}
			while( !dead && c.outPos < c.out.size() )
			{
				const ssize_t n = write( c.fd, c.out.data() + c.outPos, c.out.size() - c.outPos );
				if( n > 0 ) c.outPos += (std::size_t)n;
				else { if( n < 0 && errno != EAGAIN && errno != EWOULDBLOCK && errno != EINTR ) dead = true; break; }
			}
			if( c.outPos == c.out.size() ) { c.out.clear(); c.outPos = 0; if( c.closeAfterWrite ) dead = true; }
			if( dead ) { close( c.fd ); c.fd = -1; }
		}
		clients.erase( std::remove_if( clients.begin(), clients.end(), []( const Client& c ) { return c.fd < 0; } ), clients.end() );
		if( !clients.empty() ) idleSince = NowMs();
		// One request per client per turn, newest first: older complete requests are answered "dropped".
		for( std::size_t k = 0; k < clients.size(); ++k )
		{
			Client& c = clients[ ( next + k ) % clients.size() ];
			Request q, newest;
			std::size_t at = 0, newestAt = 0;
			long newestSize = 0;
			for( ;; )
			{
				const long size = ParseRequest( c.in.data() + at, c.in.size() - at, q );
				if( size == 0 ) break;
				if( size < 0 )// unrecoverable framing: answer, drop everything buffered and the connection
				{
					Reply( c, q, ST_BAD_REQUEST, "malformed request" );
					at = c.in.size();
					newestSize = 0;
					c.closeAfterWrite = true;
					break;
				}
				if( newestSize ) Reply( c, newest, ST_DROPPED, "superseded by a newer frame" );
				newest = q;
				newestAt = at;
				newestSize = size;
				at += (std::size_t)size;
			}
			if( newestSize )
			{
				Serve( e, c, newest, c.in.data() + newestAt + REQ_SIZE, NowMs() );
				// flush what we can at once; the rest goes out on POLLOUT
				while( c.outPos < c.out.size() )
				{
					const ssize_t n = write( c.fd, c.out.data() + c.outPos, c.out.size() - c.outPos );
					if( n > 0 ) c.outPos += (std::size_t)n;
					else break;
				}
			}
			if( at ) c.in.erase( c.in.begin(), c.in.begin() + (long)std::min( at, c.in.size() ) );
		}
		if( !clients.empty() ) next = ( next + 1 ) % clients.size();
	}
	for( Client& c : clients ) close( c.fd );
	close( lfd );
	unlink( path.c_str() );
	return 0;
}

// ---------------------------------------------------------------- oneshot (standalone check from an image file)
// The image drawn into a w x h BGRA buffer (premultiplied, rows bottom-up when bottomUp). w <= 0: the SegReadSize of
// PersonKeyLogic.h (long side 512, aspect kept, short side >= 128, multiples of 4), as the TD side computes it.
bool LoadBgra( const std::string& path, int& w, int& h, bool bottomUp, std::vector< std::uint8_t >& px )
{
	CGImageSourceRef src = CGImageSourceCreateWithURL( (__bridge CFURLRef)[NSURL fileURLWithPath:@( path.c_str() )], nullptr );
	CGImageRef img = src ? CGImageSourceCreateImageAtIndex( src, 0, nullptr ) : nullptr;
	if( !img ) { if( src ) CFRelease( src ); return false; }
	const float aspect = (float)CGImageGetWidth( img ) / (float)std::max< size_t >( CGImageGetHeight( img ), 1 );
	if( w <= 0 )
	{
		w = 512; h = 512;
		if( aspect >= 1.f ) h = (int)std::lround( 512.f / aspect ); else w = (int)std::lround( 512.f * aspect );
		w = std::max( 128, w ) / 4 * 4;
		h = std::max( 128, h ) / 4 * 4;
	}
	std::vector< std::uint8_t > top( (size_t)w * h * 4 );
	CGColorSpaceRef rgb = CGColorSpaceCreateDeviceRGB();
	CGContextRef ctx = CGBitmapContextCreate( top.data(), w, h, 8, w * 4, rgb, kCGImageAlphaPremultipliedFirst | kCGBitmapByteOrder32Little );
	CGContextDrawImage( ctx, CGRectMake( 0, 0, w, h ), img );// bitmap row 0 = top
	CGContextRelease( ctx );
	CGColorSpaceRelease( rgb );
	CGImageRelease( img );
	CFRelease( src );
	px.resize( top.size() );
	for( int y = 0; y < h; ++y ) std::memcpy( &px[ (size_t)y * w * 4 ], &top[ (size_t)( bottomUp ? h - 1 - y : y ) * w * 4 ], (size_t)w * 4 );
	return true;
}

bool WriteGrayPng( const std::string& path, const std::vector< std::uint8_t >& glRows, int w, int h )
{
	std::vector< std::uint8_t > top( glRows.size() );
	for( int y = 0; y < h; ++y ) std::memcpy( &top[ (size_t)y * w ], &glRows[ (size_t)( h - 1 - y ) * w ], (size_t)w );
	CGColorSpaceRef gray = CGColorSpaceCreateDeviceGray();
	CGContextRef ctx = CGBitmapContextCreate( top.data(), w, h, 8, w, gray, kCGImageAlphaNone );
	CGImageRef img = CGBitmapContextCreateImage( ctx );
	CGImageDestinationRef dst = CGImageDestinationCreateWithURL( (__bridge CFURLRef)[NSURL fileURLWithPath:@( path.c_str() )],
	                                                             (__bridge CFStringRef)UTTypePNG.identifier, 1, nullptr );
	bool ok = false;
	if( dst ) { CGImageDestinationAddImage( dst, img, nullptr ); ok = CGImageDestinationFinalize( dst ); CFRelease( dst ); }
	CGImageRelease( img );
	CGContextRelease( ctx );
	CGColorSpaceRelease( gray );
	return ok;
}

// Faces on one still, read at <= 960 px wide (Tracker's detect_size), both row orders: the boxes must agree.
int RunFacesOneshot( Engine& e, const std::string& in, int repeat )
{
	e.wantDepth = e.wantSeg = false;
	const double t0 = NowMs();
	e.StartLoading( true );
	const double warmWall = NowMs() - t0;
	int w = 0, h = 0;
	{
		CGImageSourceRef src = CGImageSourceCreateWithURL( (__bridge CFURLRef)[NSURL fileURLWithPath:@( in.c_str() )], nullptr );
		CGImageRef img = src ? CGImageSourceCreateImageAtIndex( src, 0, nullptr ) : nullptr;
		if( !img ) { if( src ) CFRelease( src ); std::fprintf( stderr, "cannot read %s\n", in.c_str() ); return 1; }
		const int iw = (int)CGImageGetWidth( img ), ih = (int)CGImageGetHeight( img );
		w = std::max( 4, std::min( iw, 960 ) / 4 * 4 );
		h = std::max( 1, (int)std::lround( (double)ih * w / std::max( iw, 1 ) ) );
		CGImageRelease( img );
		CFRelease( src );
	}
	std::string out = "{\"ok\":true,\"kind\":\"faces\",\"w\":" + std::to_string( w ) + ",\"h\":" + std::to_string( h );
	char buf[ 64 ];
	std::snprintf( buf, sizeof buf, ",\"warm_wall_ms\":%.1f", warmWall );
	out += buf;
	for( int pass = 0; pass < 2; ++pass )
	{
		const bool bottomUp = pass == 0;
		std::vector< std::uint8_t > px;
		int ww = w, hh = h;
		if( !LoadBgra( in, ww, hh, bottomUp, px ) ) { std::fprintf( stderr, "cannot read %s\n", in.c_str() ); return 1; }
		std::vector< float > f;
		std::string times, err;
		for( int i = 0; i < std::max( repeat, 1 ); ++i )
		{
			double ms = 0;
			err = e.Faces( px.data(), ww, hh, bottomUp, f, ms );
			if( !err.empty() ) break;
			std::snprintf( buf, sizeof buf, "%s%.2f", times.empty() ? "" : ",", ms );
			times += buf;
		}
		if( !err.empty() ) { std::printf( "{\"ok\":false,\"error\":\"%s\"}\n", JsonEscape( err ).c_str() ); return 1; }
		out += std::string( bottomUp ? ",\"bottom_up\":{" : ",\"top_down\":{" ) + "\"compute_ms\":[" + times + "],\"faces\":[";
		for( size_t k = 0; k + 5 < f.size(); k += 6 )
		{
			char fb[ 192 ];
			std::snprintf( fb, sizeof fb, "%s[%.5f,%.5f,%.5f,%.5f,%.5f,%.4f]", k ? "," : "", f[ k ], f[ k + 1 ], f[ k + 2 ], f[ k + 3 ], f[ k + 4 ], f[ k + 5 ] );
			out += fb;
		}
		out += "]}";
	}
	std::printf( "%s,\"info\":%s}\n", out.c_str(), e.InfoJson().c_str() );
	return 0;
}

int RunOneshot( Engine& e, const std::string& kind, const std::string& in, const std::string& outPng, const std::string& raw, int repeat )
{
	const bool depth = kind == "depth";
	if( kind == "faces" ) return RunFacesOneshot( e, in, repeat );
	if( !depth && kind != "seg-fast" && kind != "seg-balanced" ) { std::fprintf( stderr, "unknown --kind %s\n", kind.c_str() ); return 2; }
	e.wantDepth = depth;
	e.wantSeg = !depth;
	e.wantFaces = false;
	const double t0 = NowMs();
	e.StartLoading( true );
	const double loadWall = NowMs() - t0;
	if( depth && !e.depthReady ) { std::printf( "{\"ok\":false,\"error\":\"%s\"}\n", JsonEscape( e.depthError ).c_str() ); return 1; }
	std::vector< std::uint8_t > px;
	int w = depth ? 518 : 0, h = depth ? 392 : 0;// DepthFX reads 518x392 (the model's input); PersonKey SegReadSize
	if( !LoadBgra( in, w, h, true, px ) ) { std::fprintf( stderr, "cannot read %s\n", in.c_str() ); return 1; }
	std::vector< double > times;
	std::vector< std::uint8_t > gray;
	int ow = 0, oh = 0;
	float lo = 0, hi = 0;
	std::string err;
	for( int i = 0; i < std::max( repeat, 1 ); ++i )
	{
		double ms = 0;
		if( depth )
		{
			std::vector< float > d;
			err = e.Depth( px.data(), w, h, true, d, ow, oh, ms );
			if( !err.empty() ) break;
			const stagelab::DepthRange p = stagelab::Percentiles( d.data(), d.size() );
			lo = p.lo; hi = p.hi;
			gray.resize( d.size() );
			for( size_t k = 0; k < d.size(); ++k ) gray[ k ] = (std::uint8_t)std::lround( 255.f * std::clamp( ( d[ k ] - lo ) / std::max( hi - lo, 1e-4f ), 0.f, 1.f ) );
			if( i == 0 && !raw.empty() ) { FILE* f = std::fopen( raw.c_str(), "wb" ); if( f ) { std::fwrite( d.data(), 4, d.size(), f ); std::fclose( f ); } }
		}
		else
		{
			std::vector< std::uint8_t > inst;
			int iw = 0, ih = 0;
			err = e.Seg( px.data(), w, h, true, kind == "seg-balanced", false, gray, ow, oh, inst, iw, ih, ms );
			if( !err.empty() ) break;
			if( i == 0 && !raw.empty() ) { FILE* f = std::fopen( raw.c_str(), "wb" ); if( f ) { std::fwrite( gray.data(), 1, gray.size(), f ); std::fclose( f ); } }
		}
		times.push_back( ms );
	}
	if( !err.empty() ) { std::printf( "{\"ok\":false,\"error\":\"%s\"}\n", JsonEscape( err ).c_str() ); return 1; }
	if( !outPng.empty() && !WriteGrayPng( outPng, gray, ow, oh ) ) { std::fprintf( stderr, "cannot write %s\n", outPng.c_str() ); return 1; }
	std::string ts;
	for( double t : times ) { char b[ 32 ]; std::snprintf( b, sizeof b, "%s%.2f", ts.empty() ? "" : ",", t ); ts += b; }
	std::printf( "{\"ok\":true,\"kind\":\"%s\",\"in_w\":%d,\"in_h\":%d,\"out_w\":%d,\"out_h\":%d,\"p_lo\":%.5f,\"p_hi\":%.5f,"
	             "\"load_wall_ms\":%.1f,\"compute_ms\":[%s],\"info\":%s}\n",
	             kind.c_str(), w, h, ow, oh, lo, hi, loadWall, ts.c_str(), e.InfoJson().c_str() );
	return 0;
}
}// namespace

int main( int argc, char** argv )
{
	@autoreleasepool
	{
		if( argc < 2 ) { std::fprintf( stderr, "usage: jzb_vision_bridge info | serve --socket P ... | oneshot --kind K --in IMG --out PNG\n" ); return 2; }
		const std::string mode = argv[ 1 ];
		Engine e;
		e.modelPath = DefaultModelPath();
		std::string sock, kind, in, out, raw;
		int parentPid = 0, repeat = 1;
		double idleExit = 0;
		for( int i = 2; i < argc; ++i )
		{
			const std::string a = argv[ i ];
			auto val = [&]() -> std::string { return i + 1 < argc ? argv[ ++i ] : std::string(); };
			if( a == "--socket" ) sock = val();
			else if( a == "--model" ) e.modelPath = val();
			else if( a == "--no-depth" ) e.wantDepth = false;
			else if( a == "--no-seg" ) e.wantSeg = false;
			else if( a == "--no-faces" ) e.wantFaces = false;
			else if( a == "--no-landmarks" ) e.wantLandmarks = false;
			else if( a == "--parent-pid" ) parentPid = std::atoi( val().c_str() );
			else if( a == "--idle-exit" ) idleExit = std::atof( val().c_str() );
			else if( a == "--kind" ) kind = val();
			else if( a == "--in" ) in = val();
			else if( a == "--out" ) out = val();
			else if( a == "--raw" ) raw = val();
			else if( a == "--repeat" ) repeat = std::atoi( val().c_str() );
			else if( a == "--compute" )
			{
				const std::string c = val();
				e.units = c == "cpu" ? MLComputeUnitsCPUOnly : c == "all" ? MLComputeUnitsAll : MLComputeUnitsCPUAndNeuralEngine;
			}
			else { std::fprintf( stderr, "unknown argument %s\n", a.c_str() ); return 2; }
		}
		if( mode == "info" ) { std::printf( "%s\n", e.InfoJson().c_str() ); return 0; }
		if( mode == "serve" )
		{
			if( sock.empty() ) { std::fprintf( stderr, "serve needs --socket\n" ); return 2; }
			return RunServer( e, sock, parentPid, idleExit );
		}
		if( mode == "oneshot" ) return RunOneshot( e, kind, in, out, raw, repeat );
		std::fprintf( stderr, "unknown mode %s\n", mode.c_str() );
		return 2;
	}
}
