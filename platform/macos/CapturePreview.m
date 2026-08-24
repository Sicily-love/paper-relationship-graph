#import <Cocoa/Cocoa.h>
#import <WebKit/WebKit.h>


@interface PaperAtlasPreviewDelegate : NSObject <WKNavigationDelegate>
@property(nonatomic, strong) NSWindow *window;
@property(nonatomic, strong) WKWebView *webView;
@property(nonatomic, strong) NSURL *outputURL;
@property(nonatomic) int exitStatus;
@end


@implementation PaperAtlasPreviewDelegate

- (void)finishWithStatus:(int)status message:(NSString *)message {
    self.exitStatus = status;
    if (message.length > 0) {
        fprintf(stderr, "%s\n", message.UTF8String);
    }
    [NSApp terminate:nil];
}

- (void)capturePreview {
    WKSnapshotConfiguration *configuration = [[WKSnapshotConfiguration alloc] init];
    configuration.rect = NSMakeRect(0, 0, 1440, 1000);
    configuration.snapshotWidth = @1440;

    __weak typeof(self) weakSelf = self;
    [self.webView takeSnapshotWithConfiguration:configuration
                              completionHandler:^(NSImage *image, NSError *error) {
        PaperAtlasPreviewDelegate *strongSelf = weakSelf;
        if (strongSelf == nil) return;
        if (image == nil || error != nil) {
            [strongSelf finishWithStatus:1
                                 message:[NSString stringWithFormat:@"WebKit 截图失败：%@",
                                          error.localizedDescription ?: @"未知错误"]];
            return;
        }

        CGImageRef cgImage = [image CGImageForProposedRect:NULL context:nil hints:nil];
        if (cgImage == NULL) {
            [strongSelf finishWithStatus:1 message:@"WebKit 截图无法转换为 PNG。"];
            return;
        }
        NSBitmapImageRep *representation = [[NSBitmapImageRep alloc] initWithCGImage:cgImage];
        NSData *png = [representation representationUsingType:NSBitmapImageFileTypePNG properties:@{}];
        NSError *writeError = nil;
        if (png == nil || ![png writeToURL:strongSelf.outputURL
                                   options:NSDataWritingAtomic
                                     error:&writeError]) {
            [strongSelf finishWithStatus:1
                                 message:[NSString stringWithFormat:@"写入预览图失败：%@",
                                          writeError.localizedDescription ?: @"未知错误"]];
            return;
        }
        [strongSelf finishWithStatus:0 message:nil];
    }];
}

- (void)webView:(WKWebView *)webView didFinishNavigation:(WKNavigation *)navigation {
    dispatch_after(dispatch_time(DISPATCH_TIME_NOW, (int64_t)(1.2 * NSEC_PER_SEC)),
                   dispatch_get_main_queue(), ^{
        [self capturePreview];
    });
}

- (void)webView:(WKWebView *)webView
        didFailNavigation:(WKNavigation *)navigation
                withError:(NSError *)error {
    [self finishWithStatus:1
                   message:[NSString stringWithFormat:@"预览页面加载失败：%@", error.localizedDescription]];
}

- (void)webView:(WKWebView *)webView
        didFailProvisionalNavigation:(WKNavigation *)navigation
                           withError:(NSError *)error {
    [self finishWithStatus:1
                   message:[NSString stringWithFormat:@"预览页面无法打开：%@", error.localizedDescription]];
}

@end


int main(int argc, const char *argv[]) {
    @autoreleasepool {
        if (argc != 3) {
            fprintf(stderr, "usage: CapturePreview <index.html> <output.png>\n");
            return 2;
        }

        NSURL *inputURL = [NSURL fileURLWithPath:[NSString stringWithUTF8String:argv[1]]];
        NSURL *outputURL = [NSURL fileURLWithPath:[NSString stringWithUTF8String:argv[2]]];
        if (![NSFileManager.defaultManager fileExistsAtPath:inputURL.path]) {
            fprintf(stderr, "preview source does not exist: %s\n", inputURL.path.UTF8String);
            return 2;
        }

        NSApplication *application = NSApplication.sharedApplication;
        application.activationPolicy = NSApplicationActivationPolicyProhibited;

        PaperAtlasPreviewDelegate *delegate = [[PaperAtlasPreviewDelegate alloc] init];
        delegate.outputURL = outputURL;
        delegate.exitStatus = 1;
        delegate.window = [[NSWindow alloc]
            initWithContentRect:NSMakeRect(0, 0, 1440, 1000)
                      styleMask:NSWindowStyleMaskBorderless
                        backing:NSBackingStoreBuffered
                          defer:NO];

        WKWebViewConfiguration *webConfiguration = [[WKWebViewConfiguration alloc] init];
        webConfiguration.websiteDataStore = WKWebsiteDataStore.nonPersistentDataStore;
        delegate.webView = [[WKWebView alloc]
            initWithFrame:NSMakeRect(0, 0, 1440, 1000)
            configuration:webConfiguration];
        delegate.webView.navigationDelegate = delegate;
        delegate.window.contentView = delegate.webView;
        [delegate.window orderBack:nil];

        NSURL *webRoot = inputURL.URLByDeletingLastPathComponent;
        [delegate.webView loadFileURL:inputURL allowingReadAccessToURL:webRoot];
        [application run];
        return delegate.exitStatus;
    }
}
