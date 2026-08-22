#import <AppKit/AppKit.h>

static NSData *renderIcon(NSImage *source, NSInteger pixels) {
    NSBitmapImageRep *bitmap = [[NSBitmapImageRep alloc]
        initWithBitmapDataPlanes:NULL
        pixelsWide:pixels
        pixelsHigh:pixels
        bitsPerSample:8
        samplesPerPixel:4
        hasAlpha:YES
        isPlanar:NO
        colorSpaceName:NSDeviceRGBColorSpace
        bytesPerRow:0
        bitsPerPixel:0];
    bitmap.size = NSMakeSize(pixels, pixels);
    NSGraphicsContext *context = [NSGraphicsContext graphicsContextWithBitmapImageRep:bitmap];
    if (context == nil) return nil;

    [NSGraphicsContext saveGraphicsState];
    NSGraphicsContext.currentContext = context;
    context.imageInterpolation = NSImageInterpolationHigh;
    [NSColor.clearColor setFill];
    NSRectFill(NSMakeRect(0, 0, pixels, pixels));

    CGFloat scale = pixels / 1024.0;
    NSRect iconBounds = NSMakeRect(40 * scale, 40 * scale, 944 * scale, 944 * scale);
    [[NSBezierPath bezierPathWithRoundedRect:iconBounds
                                    xRadius:204 * scale
                                    yRadius:204 * scale] addClip];
    [source drawInRect:NSMakeRect(0, 0, pixels, pixels)
              fromRect:NSMakeRect(100, 100, 1054, 1054)
             operation:NSCompositingOperationCopy
              fraction:1.0
        respectFlipped:YES
                 hints:@{NSImageHintInterpolation: @(NSImageInterpolationHigh)}];
    [context flushGraphics];
    [NSGraphicsContext restoreGraphicsState];
    return [bitmap representationUsingType:NSBitmapImageFileTypePNG properties:@{}];
}

static void appendIconElement(NSMutableData *container, const char type[4], NSData *payload) {
    [container appendBytes:type length:4];
    uint32_t elementSize = CFSwapInt32HostToBig((uint32_t)payload.length + 8);
    [container appendBytes:&elementSize length:sizeof(elementSize)];
    [container appendData:payload];
}

int main(int argc, const char *argv[]) {
    @autoreleasepool {
        if (argc != 4) {
            fprintf(stderr, "usage: PrepareIcon source.png output.png output.icns\n");
            return 2;
        }

        NSString *sourcePath = [NSString stringWithUTF8String:argv[1]];
        NSString *outputPath = [NSString stringWithUTF8String:argv[2]];
        NSString *icnsPath = [NSString stringWithUTF8String:argv[3]];
        NSImage *source = [[NSImage alloc] initWithContentsOfFile:sourcePath];
        if (source == nil) {
            fprintf(stderr, "cannot load source icon\n");
            return 1;
        }

        NSData *master = renderIcon(source, 1024);
        if (master == nil || ![master writeToFile:outputPath atomically:YES]) return 1;

        NSMutableData *elements = [NSMutableData data];
        struct IconSize { const char *type; NSInteger pixels; } sizes[] = {
            {"icp4", 16}, {"icp5", 32}, {"icp6", 64}, {"ic07", 128},
            {"ic08", 256}, {"ic09", 512}, {"ic10", 1024}, {"ic11", 32},
            {"ic12", 64}, {"ic13", 256}, {"ic14", 512},
        };
        for (NSUInteger index = 0; index < sizeof(sizes) / sizeof(sizes[0]); index++) {
            NSData *png = renderIcon(source, sizes[index].pixels);
            appendIconElement(elements, sizes[index].type, png);
        }

        NSMutableData *container = [NSMutableData dataWithBytes:"icns" length:4];
        uint32_t totalSize = CFSwapInt32HostToBig((uint32_t)elements.length + 8);
        [container appendBytes:&totalSize length:sizeof(totalSize)];
        [container appendData:elements];
        return [container writeToFile:icnsPath atomically:YES] ? 0 : 1;
    }
}
