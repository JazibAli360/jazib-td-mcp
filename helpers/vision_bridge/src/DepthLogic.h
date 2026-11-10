#pragma once
// td-port copy (2026-10-14) of stagelab ffgl/common/DepthLogic.h at HEAD ad2c5bb (last changed 1adf506),
// sha1 c80fc2eef352. Unchanged below this comment. The bridge uses Percentiles() only; lib/depth_fx.py ports the
// rest to Python and tests/test_depth_fx.py checks it against values printed from this file.
// JZBV_DepthFX's host-independent logic (docs/specs/10-camera.md "JZBV_DepthFX"; research.md round 21): the model's
// relative depth (larger = nearer, any scale) becomes a steady 0..1 "nearness". The range is taken from robust
// percentiles (2 % / 98 %, so a stray hot pixel does not squash the frame) and eased over time, and every pixel is eased
// toward each new result, so one person walking up to the camera does not make the whole picture pump. All in seconds
// (directive 16). Pure C++, header-only; tested by ffgl/tests/depth_logic_test.cpp.
#include <algorithm>
#include <cmath>
#include <cstddef>
#include <vector>

namespace stagelab
{
struct DepthRange { float lo = 0.f, hi = 1.f; };

// The low / high percentile of `v` (n values), via a 1024-bin histogram over its min..max.
inline DepthRange Percentiles( const float* v, std::size_t n, float lowShare = 0.02f, float highShare = 0.98f )
{
	DepthRange r;
	if( n == 0 ) return r;
	float mn = v[ 0 ], mx = v[ 0 ];
	for( std::size_t i = 1; i < n; ++i ) { mn = std::min( mn, v[ i ] ); mx = std::max( mx, v[ i ] ); }
	if( !( mx > mn ) ) { r.lo = mn; r.hi = mn + 1e-3f; return r; }
	constexpr int BINS = 1024;
	std::vector< std::size_t > h( BINS, 0 );
	const float k = ( BINS - 1 ) / ( mx - mn );
	for( std::size_t i = 0; i < n; ++i ) ++h[ (std::size_t)std::clamp( (int)( ( v[ i ] - mn ) * k ), 0, BINS - 1 ) ];
	const std::size_t lowN = (std::size_t)( lowShare * n ), highN = (std::size_t)( highShare * n );
	std::size_t acc = 0;
	int lo = 0, hi = BINS - 1;
	bool haveLo = false;
	for( int b = 0; b < BINS; ++b )
	{
		acc += h[ b ];
		if( !haveLo && acc > lowN ) { lo = b; haveLo = true; }
		if( acc >= highN ) { hi = b; break; }
	}
	r.lo = mn + lo / k;
	r.hi = std::max( mn + ( hi + 1 ) / k, r.lo + 1e-3f );
	return r;
}

// Exponential ease with time constant `tau` seconds over `dt` seconds: the share of the way to go this step.
inline float EaseStep( float dt, float tau ) { return tau <= 1e-4f ? 1.f : 1.f - std::exp( -std::max( dt, 0.f ) / tau ); }

// Smoothing 0..1 -> time constant: 0 = take every result as is, 1 = 0.6 s.
inline float DepthTau( float smoothing ) { return 0.6f * std::clamp( smoothing, 0.f, 1.f ); }

// The eased depth map (0..1 nearness), updated per model result. First result is taken as is.
class DepthField
{
public:
	// `raw`: the model's w x h values (any scale, larger = nearer); dt: seconds since the previous result.
	void Add( const float* raw, int w, int h, float dt, float smoothing )
	{
		const std::size_t n = (std::size_t)std::max( w, 0 ) * std::max( h, 0 );
		const DepthRange p = Percentiles( raw, n );
		const bool first = field.size() != n || w != width;
		const float kRange = first ? 1.f : EaseStep( dt, std::max( DepthTau( smoothing ), 0.25f ) );// the range eases at least 0.25 s
		range.lo += ( p.lo - range.lo ) * kRange;
		range.hi += ( p.hi - range.hi ) * kRange;
		const float span = std::max( range.hi - range.lo, 1e-4f );
		const float k = first ? 1.f : EaseStep( dt, DepthTau( smoothing ) );
		if( first ) { field.assign( n, 0.f ); width = w; height = h; }
		for( std::size_t i = 0; i < n; ++i )
		{
			const float d = std::clamp( ( raw[ i ] - range.lo ) / span, 0.f, 1.f );
			field[ i ] += ( d - field[ i ] ) * k;
		}
		++results;
	}
	const std::vector< float >& Field() const { return field; }// row-major as given, 0 (far) .. 1 (near)
	int Width() const { return width; }
	int Height() const { return height; }
	int Results() const { return results; }
	DepthRange Range() const { return range; }

private:
	std::vector< float > field;
	DepthRange range;
	int width = 0, height = 0, results = 0;
};
}// namespace stagelab
