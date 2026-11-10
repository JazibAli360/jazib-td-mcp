#include "AppleVisionMask.h"
#include <algorithm>
#include <iostream>

extern "C" {
DLLEXPORT
void FillTOPPluginInfo(TD::TOP_PluginInfo *info) {
  if (!info->setAPIVersion(TD::TOPCPlusPlusAPIVersion)) {
    return;
  }
  info->executeMode = TD::TOP_ExecuteMode::CPUMem;

  info->customOPInfo.opType->setString("Applevisionmask");
  info->customOPInfo.opLabel->setString("Apple Vision Mask");
  info->customOPInfo.opIcon->setString("AVM");
  info->customOPInfo.authorName->setString("Author Name");
  info->customOPInfo.authorEmail->setString("email@email.com");

  info->customOPInfo.minInputs = 1;
  info->customOPInfo.maxInputs = 1;
}

DLLEXPORT
TD::TOP_CPlusPlusBase *CreateTOPInstance(const TD::OP_NodeInfo *info,
                                         TD::TOP_Context *context) {
  return new AppleVisionMask(info, context);
}

DLLEXPORT
void DestroyTOPInstance(TD::TOP_CPlusPlusBase *instance,
                        TD::TOP_Context *context) {
  delete (AppleVisionMask *)instance;
}
};

AppleVisionMask::AppleVisionMask(const TD::OP_NodeInfo *info,
                                 TD::TOP_Context *context)
    : myContext(context), myExecuteCount(0) {
  currentQualityLevel = 1;
  segmentationRequest = [[VNGeneratePersonSegmentationRequest alloc] init];
  segmentationRequest.qualityLevel =
      VNGeneratePersonSegmentationRequestQualityLevelBalanced;
  segmentationRequest.outputPixelFormat = kCVPixelFormatType_OneComponent8;

  processingQueue = dispatch_queue_create("com.applevisionmask.processing",
                                          DISPATCH_QUEUE_SERIAL);
}

AppleVisionMask::~AppleVisionMask() {
  // Wait for any in-flight processing to complete before destroying
  dispatch_sync(processingQueue, ^{
                });

  if (inputPool) {
    CVPixelBufferPoolRelease(inputPool);
  }
}

void AppleVisionMask::getGeneralInfo(TD::TOP_GeneralInfo *ginfo,
                                     const TD::OP_Inputs *inputs,
                                     void *reserved1) {
  ginfo->cookEveryFrame = true;
}

void AppleVisionMask::ensurePool(size_t width, size_t height) {
  if (inputPool && inputPoolW == width && inputPoolH == height)
    return;

  if (inputPool) {
    CVPixelBufferPoolRelease(inputPool);
    inputPool = nullptr;
  }

  NSDictionary *poolAttrs =
      @{(NSString *)kCVPixelBufferPoolMinimumBufferCountKey : @3};
  NSDictionary *bufferAttrs = @{
    (NSString *)kCVPixelBufferWidthKey : @(width),
    (NSString *)kCVPixelBufferHeightKey : @(height),
    (NSString *)kCVPixelBufferPixelFormatTypeKey : @(kCVPixelFormatType_32BGRA),
    (NSString *)kCVPixelBufferIOSurfacePropertiesKey : @{}
  };

  CVPixelBufferPoolCreate(kCFAllocatorDefault,
                          (__bridge CFDictionaryRef)poolAttrs,
                          (__bridge CFDictionaryRef)bufferAttrs, &inputPool);
  inputPoolW = width;
  inputPoolH = height;
}

void AppleVisionMask::runSegmentation(CVPixelBufferRef inputBuffer,
                                      uint32_t sequence, int qualityLevel) {
  @autoreleasepool {
    switch (qualityLevel) {
    case 0:
      segmentationRequest.qualityLevel =
          VNGeneratePersonSegmentationRequestQualityLevelAccurate;
      break;
    case 1:
      segmentationRequest.qualityLevel =
          VNGeneratePersonSegmentationRequestQualityLevelBalanced;
      break;
    case 2:
      segmentationRequest.qualityLevel =
          VNGeneratePersonSegmentationRequestQualityLevelFast;
      break;
    }

    VNImageRequestHandler *handler =
        [[VNImageRequestHandler alloc] initWithCVPixelBuffer:inputBuffer
                                                     options:@{}];
    NSError *error = nil;
    [handler performRequests:@[ segmentationRequest ] error:&error];

    if (!error && segmentationRequest.results.count > 0) {
      VNPixelBufferObservation *observation =
          segmentationRequest.results.firstObject;
      CVPixelBufferRef maskBuf = observation.pixelBuffer;

      if (maskBuf) {
        CVPixelBufferLockBaseAddress(maskBuf, kCVPixelBufferLock_ReadOnly);

        size_t mw = CVPixelBufferGetWidth(maskBuf);
        size_t mh = CVPixelBufferGetHeight(maskBuf);
        uint8_t *maskData = (uint8_t *)CVPixelBufferGetBaseAddress(maskBuf);
        size_t maskBPR = CVPixelBufferGetBytesPerRow(maskBuf);

        {
          std::lock_guard<std::mutex> lock(maskMutex);
          MaskData md;
          md.sequence = sequence;
          md.width = mw;
          md.height = mh;
          md.mask.assign(maskData, maskData + (mw * mh));
          if (maskBPR != mw) {
            md.mask.resize(mw * mh);
            for (size_t y = 0; y < mh; ++y) {
              memcpy(md.mask.data() + y * mw, maskData + y * maskBPR, mw);
            }
          }
          // Only keep the most recent mask history to avoid memory bloat
          if (maskHistory.size() > 10)
            maskHistory.pop_front();
          maskHistory.push_back(std::move(md));
        }

        CVPixelBufferUnlockBaseAddress(maskBuf, kCVPixelBufferLock_ReadOnly);
      }
    }

    CVPixelBufferRelease(inputBuffer);
    isProcessing.store(false);
  }
}

void AppleVisionMask::setupParameters(TD::OP_ParameterManager *manager,
                                      void *reserved1) {
  // Opacity
  {
    TD::OP_NumericParameter np;
    np.name = "Opacity";
    np.label = "Background Opacity";
    np.defaultValues[0] = 1.0;
    np.minSliders[0] = 0.0;
    np.maxSliders[0] = 1.0;
    manager->appendFloat(np);
  }

  // Output Mode
  {
    TD::OP_StringParameter sp;
    sp.name = "Outputmode";
    sp.label = "Output Mode";
    sp.defaultValue = "Maskonly";
    const char *names[] = {"Composited", "Maskonly"};
    const char *labels[] = {"Composited (White Silhouette)",
                            "Mask Only (Alpha 8-bit)"};
    manager->appendMenu(sp, 2, names, labels);
  }

  // Quality Level
  {
    TD::OP_StringParameter sp;
    sp.name = "Quality";
    sp.label = "Vision Quality";
    sp.defaultValue = "Balanced";
    const char *names[] = {"Accurate", "Balanced", "Fast"};
    const char *labels[] = {"Accurate", "Balanced", "Fast"};
    manager->appendMenu(sp, 3, names, labels);
  }

  // Synchronization Delay
  {
    TD::OP_NumericParameter np;
    np.name = "Syncframes";
    np.label = "Sync Delay (Frames)";
    np.defaultValues[0] = 3;
    np.minSliders[0] = 0;
    np.maxSliders[0] = 10;
    np.clampMins[0] = true;
    manager->appendInt(np);
  }

  // Process Every N Frames
  {
    TD::OP_NumericParameter np;
    np.name = "Processinterval";
    np.label = "Process Every N Frames";
    np.defaultValues[0] = 1;
    np.minSliders[0] = 1;
    np.maxSliders[0] = 10;
    manager->appendInt(np);
  }

  // Output Resolution
  {
    TD::OP_StringParameter sp;
    sp.name = "Nativeresolution";
    sp.label = "Output Resolution";
    sp.defaultValue = "Input";
    const char *names[] = {"Input", "Native"};
    const char *labels[] = {"Match Input Resolution",
                            "Native Mask Resolution (Faster)"};
    manager->appendMenu(sp, 2, names, labels);
  }
}

void AppleVisionMask::pulsePressed(const char *name, void *reserved1) {}

int32_t AppleVisionMask::getNumInfoCHOPChans(void *reserved1) { return 2; }

void AppleVisionMask::getInfoCHOPChan(int32_t index, TD::OP_InfoCHOPChan *chan,
                                      void *reserved1) {
  if (index == 0) {
    chan->name->setString("latency_frames");
    chan->value = (float)lastMeasuredLatency;
  } else if (index == 1) {
    chan->name->setString("queue_size");
    chan->value = (float)pendingFrames.size();
  }
}

void AppleVisionMask::execute(TD::TOP_Output *output,
                              const TD::OP_Inputs *inputs, void *reserved1) {
  myExecuteCount++;

  // 1. Read parameters
  double opacityVal = inputs->getParDouble("Opacity");
  int outputModeIndex = inputs->getParInt("Outputmode");
  int qualityIndex = inputs->getParInt("Quality");
  int processInterval = std::max(1, (int)inputs->getParInt("Processinterval"));
  int nativeRes = inputs->getParInt("Nativeresolution");
  int syncDelay = std::max(0, (int)inputs->getParInt("Syncframes"));

  if (qualityIndex != currentQualityLevel) {
    currentQualityLevel = qualityIndex;
  }

  int opacityInt = (int)(opacityVal * 256.0);

  // 2. Get input
  if (inputs->getNumInputs() <= 0)
    return;
  const TD::OP_TOPInput *input = inputs->getInputTOP(0);
  if (!input)
    return;

  TD::OP_TOPInputDownloadOptions downloadOpts;
  downloadOpts.pixelFormat = TD::OP_PixelFormat::BGRA8Fixed;
  downloadOpts.verticalFlip = true;

  TD::OP_SmartRef<TD::OP_TOPDownloadResult> downloadResult =
      input->downloadTexture(downloadOpts, nullptr);
  if (!downloadResult)
    return;

  size_t width = downloadResult->textureDesc.width;
  size_t height = downloadResult->textureDesc.height;

  // Always push every frame to pending queue
  {
    FrameData fd;
    if (!freeFrames.empty()) {
      fd = std::move(freeFrames.front());
      freeFrames.pop_front();
    }
    fd.sequence = nextSequence++;
    fd.width = width;
    fd.height = height;
    fd.bgraData.assign((uint8_t *)downloadResult->getData(),
                       (uint8_t *)downloadResult->getData() +
                           width * height * 4);
    pendingFrames.push_back(std::move(fd));
  }

  // 3. Initiate Vision processing if ready
  frameCounter++;
  if ((frameCounter % processInterval == 0) && !isProcessing.load()) {
    ensurePool(width, height);
    CVPixelBufferRef poolBuffer = nullptr;
    CVReturn cvResult =
        CVPixelBufferPoolCreatePixelBuffer(nullptr, inputPool, &poolBuffer);

    if (cvResult == kCVReturnSuccess && poolBuffer) {
      CVPixelBufferLockBaseAddress(poolBuffer, 0);
      uint8_t *destData = (uint8_t *)CVPixelBufferGetBaseAddress(poolBuffer);
      size_t destBPR = CVPixelBufferGetBytesPerRow(poolBuffer);
      uint8_t *srcData = (uint8_t *)downloadResult->getData();
      size_t srcBPR = width * 4;

      for (size_t y = 0; y < height; ++y) {
        memcpy(destData + y * destBPR, srcData + y * srcBPR, srcBPR);
      }
      CVPixelBufferUnlockBaseAddress(poolBuffer, 0);

      isProcessing.store(true);
      uint32_t seq = pendingFrames.back().sequence;
      int ql = currentQualityLevel;
      dispatch_async(processingQueue, ^{
        this->runSegmentation(poolBuffer, seq, ql);
      });
    }
  }

  // 4. Update latest mask and measure actual latency
  {
    std::lock_guard<std::mutex> lock(maskMutex);
    if (!maskHistory.empty()) {
      currentMask = std::move(maskHistory.back());
      maskHistory.clear();
      lastMeasuredLatency = nextSequence - currentMask.sequence;
      hasOutput = true;
    }
  }

  // 5. Select frame from delay line for output
  // We advance the delay line every frame to ensure 60fps video.
  if (pendingFrames.size() > (size_t)syncDelay) {
    currentFrame = std::move(pendingFrames.front());
    pendingFrames.pop_front();
  } else {
    // Queue still filling up
    return;
  }

  if (!hasOutput) {
    freeFrames.push_back(std::move(currentFrame));
    return;
  }

  // 6. Final Output (Output 0: Mask, Output 1: Delayed Original)
  size_t maskW = currentMask.width;
  size_t maskH = currentMask.height;
  uint8_t *maskData = currentMask.mask.data();

  size_t outW = (nativeRes == 1) ? maskW : currentFrame.width;
  size_t outH = (nativeRes == 1) ? maskH : currentFrame.height;

  bool sameSize = (maskW == outW && maskH == outH);
  uint32_t fpScaleX = 0, fpScaleY = 0;
  if (!sameSize) {
    fpScaleX = (uint32_t)((maskW << 16) / outW);
    fpScaleY = (uint32_t)((maskH << 16) / outH);
  }

  // --- OUTPUT 0: MASK/COMPOSITED ---
  if (outputModeIndex == 1) // Mask Only
  {
    uint64_t outSize = outW * outH * 1;
    TD::OP_SmartRef<TD::TOP_Buffer> outBuffer = myContext->createOutputBuffer(
        outSize, TD::TOP_BufferFlags::None, nullptr);
    uint8_t *outData = (uint8_t *)outBuffer->data;

    if (sameSize) {
      for (size_t y = 0; y < outH; ++y) {
        memcpy(outData + (y * outW), maskData + (y * maskW), outW);
      }
    } else {
      for (size_t y = 0; y < outH; ++y) {
        uint8_t *outRow = outData + (y * outW);
        uint32_t fpY = y * fpScaleY;
        size_t y0 = fpY >> 16, y1 = std::min(y0 + 1, maskH - 1);
        uint32_t wy = (fpY & 0xFFFF) >> 8;
        uint8_t *row0 = maskData + (y0 * maskW),
                *row1 = maskData + (y1 * maskW);
        uint32_t currentFpX = 0;
        for (size_t x = 0; x < outW; ++x) {
          size_t x0 = currentFpX >> 16, x1 = std::min(x0 + 1, maskW - 1);
          uint32_t wx = (currentFpX & 0xFFFF) >> 8;
          uint32_t top = (row0[x0] * (256 - wx) + row0[x1] * wx) >> 8;
          uint32_t bot = (row1[x0] * (256 - wx) + row1[x1] * wx) >> 8;
          outRow[x] =
              (uint8_t)(((top * (256 - wy) + bot * wy) >> 8) * opacityInt >> 8);
          currentFpX += fpScaleX;
        }
      }
    }

    TD::TOP_UploadInfo uploadInfo;
    uploadInfo.textureDesc.width = (uint32_t)outW;
    uploadInfo.textureDesc.height = (uint32_t)outH;
    uploadInfo.textureDesc.texDim = TD::OP_TexDim::e2D;
    uploadInfo.textureDesc.pixelFormat = TD::OP_PixelFormat::A8Fixed;
    uploadInfo.firstPixel = TD::TOP_FirstPixel::TopLeft;
    uploadInfo.colorBufferIndex = 0;
    output->uploadBuffer(&outBuffer, uploadInfo, nullptr);
  } else // Composited
  {
    uint64_t outSize = outW * outH * 4;
    TD::OP_SmartRef<TD::TOP_Buffer> outBuffer = myContext->createOutputBuffer(
        outSize, TD::TOP_BufferFlags::None, nullptr);
    uint32_t *outData = (uint32_t *)outBuffer->data;
    uint32_t white = 0x00FFFFFF;

    if (sameSize) {
      for (size_t y = 0; y < outH; ++y) {
        uint8_t *maskRow = maskData + (y * maskW);
        uint32_t *outRow = outData + (y * outW);
        for (size_t x = 0; x < outW; ++x) {
          outRow[x] = (((maskRow[x] * opacityInt) >> 8) << 24) | white;
        }
      }
    } else {
      for (size_t y = 0; y < outH; ++y) {
        uint32_t *outRow = outData + (y * outW);
        uint32_t fpY = y * fpScaleY;
        size_t y0 = fpY >> 16, y1 = std::min(y0 + 1, maskH - 1);
        uint32_t wy = (fpY & 0xFFFF) >> 8;
        uint8_t *row0 = maskData + (y0 * maskW),
                *row1 = maskData + (y1 * maskW);
        uint32_t currentFpX = 0;
        for (size_t x = 0; x < outW; ++x) {
          size_t x0 = currentFpX >> 16, x1 = std::min(x0 + 1, maskW - 1);
          uint32_t wx = (currentFpX & 0xFFFF) >> 8;
          uint32_t top = (row0[x0] * (256 - wx) + row0[x1] * wx) >> 8;
          uint32_t bot = (row1[x0] * (256 - wx) + row1[x1] * wx) >> 8;
          uint32_t val = (top * (256 - wy) + bot * wy) >> 8;
          outRow[x] = (((val * opacityInt) >> 8) << 24) | white;
          currentFpX += fpScaleX;
        }
      }
    }

    TD::TOP_UploadInfo uploadInfo;
    uploadInfo.textureDesc.width = (uint32_t)outW;
    uploadInfo.textureDesc.height = (uint32_t)outH;
    uploadInfo.textureDesc.texDim = TD::OP_TexDim::e2D;
    uploadInfo.textureDesc.pixelFormat = TD::OP_PixelFormat::BGRA8Fixed;
    uploadInfo.firstPixel = TD::TOP_FirstPixel::TopLeft;
    uploadInfo.colorBufferIndex = 0;
    output->uploadBuffer(&outBuffer, uploadInfo, nullptr);
  }

  // --- OUTPUT 1: DELAYED ORIGINAL ---
  {
    uint64_t outSize = currentFrame.width * currentFrame.height * 4;
    TD::OP_SmartRef<TD::TOP_Buffer> outBuffer = myContext->createOutputBuffer(
        outSize, TD::TOP_BufferFlags::None, nullptr);
    memcpy(outBuffer->data, currentFrame.bgraData.data(), outSize);

    TD::TOP_UploadInfo uploadInfo;
    uploadInfo.textureDesc.width = (uint32_t)currentFrame.width;
    uploadInfo.textureDesc.height = (uint32_t)currentFrame.height;
    uploadInfo.textureDesc.texDim = TD::OP_TexDim::e2D;
    uploadInfo.textureDesc.pixelFormat = TD::OP_PixelFormat::BGRA8Fixed;
    uploadInfo.firstPixel = TD::TOP_FirstPixel::TopLeft;
    uploadInfo.colorBufferIndex = 1;
    output->uploadBuffer(&outBuffer, uploadInfo, nullptr);
  }

  // Recyle the displayed frame
  freeFrames.push_back(std::move(currentFrame));
}
