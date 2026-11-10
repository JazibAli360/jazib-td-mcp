#include "TOP_CPlusPlusBase.h"
#include <vector>
#include <deque>
#include <mutex>
#include <atomic>
#include <dispatch/dispatch.h>

#ifdef __OBJC__
#import <Vision/Vision.h>
#import <CoreVideo/CoreVideo.h>
#import <Foundation/Foundation.h>
#endif

class AppleVisionMask : public TD::TOP_CPlusPlusBase
{
public:
	AppleVisionMask(const TD::OP_NodeInfo* info, TD::TOP_Context* context);
	virtual ~AppleVisionMask();

	virtual void		getGeneralInfo(TD::TOP_GeneralInfo* ginfo, const TD::OP_Inputs* inputs, void* reserved1) override;
	virtual void		execute(TD::TOP_Output* output, const TD::OP_Inputs* inputs, void* reserved1) override;

	virtual void		setupParameters(TD::OP_ParameterManager* manager, void* reserved1) override;
	virtual void		pulsePressed(const char* name, void* reserved1) override;

	virtual int32_t		getNumInfoCHOPChans(void* reserved1) override;
	virtual void		getInfoCHOPChan(int32_t index, TD::OP_InfoCHOPChan* chan, void* reserved1) override;

private:
	struct FrameData {
		uint32_t sequence = 0;
		std::vector<uint8_t> bgraData;
		size_t width = 0;
		size_t height = 0;
	};

	struct MaskData {
		uint32_t sequence = 0;
		std::vector<uint8_t> mask;
		size_t width = 0;
		size_t height = 0;
	};

	void				runSegmentation(CVPixelBufferRef inputBuffer, uint32_t sequence, int qualityLevel);
	void				ensurePool(size_t width, size_t height);

#ifdef __OBJC__
	VNGeneratePersonSegmentationRequest* segmentationRequest;
#else
	void* segmentationRequest;
#endif

	TD::TOP_Context*	myContext;
	int32_t				myExecuteCount;
	int					currentQualityLevel;

	// Async processing via GCD serial queue
	dispatch_queue_t	processingQueue;
	std::mutex			maskMutex;
	std::atomic<bool>	isProcessing{false};
	
	// Queue of pending frames and completed masks
	std::deque<FrameData> pendingFrames;
	std::deque<MaskData> maskHistory;
	
	// Reusable pool for FrameData to avoid reallocations
	std::deque<FrameData> freeFrames;
	
	// Current synchronized pair for output
	FrameData			currentFrame;
	MaskData			currentMask;
	bool				hasOutput = false;
	
	uint32_t			nextSequence = 0;
	uint32_t			lastMeasuredLatency = 0;
	
	// CVPixelBuffer pool for input frames
	CVPixelBufferPoolRef inputPool = nullptr;
	size_t				inputPoolW = 0;
	size_t				inputPoolH = 0;

	// Frame counter for skip logic
	uint32_t			frameCounter = 0;
};
