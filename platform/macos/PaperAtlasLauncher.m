#import <Cocoa/Cocoa.h>
#import <WebKit/WebKit.h>


@interface PaperAtlasSchemeHandler : NSObject <WKURLSchemeHandler>
@property(nonatomic, strong) NSURL *projectRoot;
@property(nonatomic, strong) NSURL *papersDirectory;
@property(nonatomic, strong) NSURL *pythonExecutable;
- (NSData *)runBackendCommand:(NSString *)command body:(NSData *)body;
@end


@implementation PaperAtlasSchemeHandler

- (instancetype)initWithProjectRoot:(NSURL *)projectRoot
                    papersDirectory:(NSURL *)papersDirectory
                   pythonExecutable:(NSURL *)pythonExecutable {
    self = [super init];
    if (self) {
        _projectRoot = projectRoot;
        _papersDirectory = papersDirectory;
        _pythonExecutable = pythonExecutable;
    }
    return self;
}

- (NSData *)requestBody:(NSURLRequest *)request {
    if (request.HTTPBody != nil) return request.HTTPBody;
    NSInputStream *stream = request.HTTPBodyStream;
    if (stream == nil) return [NSData data];
    NSMutableData *body = [NSMutableData data];
    uint8_t buffer[8192];
    [stream open];
    while (stream.hasBytesAvailable) {
        NSInteger count = [stream read:buffer maxLength:sizeof(buffer)];
        if (count <= 0) break;
        [body appendBytes:buffer length:(NSUInteger)count];
    }
    [stream close];
    return body;
}

- (NSData *)runBackendCommand:(NSString *)command body:(NSData *)body {
    NSURL *backend = [self.projectRoot URLByAppendingPathComponent:@"scripts/app_backend.py"];
    NSTask *task = [[NSTask alloc] init];
    task.executableURL = self.pythonExecutable;
    task.arguments = @[backend.path, command, @"--papers-dir", self.papersDirectory.path];
    task.currentDirectoryURL = self.projectRoot;
    NSMutableDictionary *environment = [NSProcessInfo.processInfo.environment mutableCopy];
    environment[@"PYTHONDONTWRITEBYTECODE"] = @"1";
    environment[@"PYTHONNOUSERSITE"] = @"1";
    environment[@"SSL_CERT_FILE"] = @"/etc/ssl/cert.pem";
    task.environment = environment;

    NSPipe *output = [NSPipe pipe];
    task.standardOutput = output;
    NSPipe *input = [NSPipe pipe];
    task.standardInput = input;
    NSURL *logURL = [[self.projectRoot URLByAppendingPathComponent:@".cache"]
        URLByAppendingPathComponent:@"paper-atlas-app.log"];
    NSFileHandle *log = [NSFileHandle fileHandleForWritingAtPath:logURL.path];
    [log seekToEndOfFile];
    task.standardError = log;

    NSError *error = nil;
    if (![task launchAndReturnError:&error]) {
        NSDictionary *failure = @{ @"error": [NSString stringWithFormat:@"应用操作启动失败：%@", error.localizedDescription] };
        return [NSJSONSerialization dataWithJSONObject:failure options:0 error:nil];
    }
    if (body.length > 0) [[input fileHandleForWriting] writeData:body];
    [[input fileHandleForWriting] closeFile];
    NSData *result = [[output fileHandleForReading] readDataToEndOfFile];
    [task waitUntilExit];
    if (result.length > 0) return result;
    NSDictionary *failure = @{ @"error": @"应用操作没有返回结果，请查看运行日志" };
    return [NSJSONSerialization dataWithJSONObject:failure options:0 error:nil];
}

- (NSString *)mimeTypeForPath:(NSString *)path {
    NSDictionary *types = @{
        @"html": @"text/html", @"css": @"text/css", @"js": @"text/javascript",
        @"json": @"application/json", @"png": @"image/png", @"svg": @"image/svg+xml",
        @"woff2": @"font/woff2",
    };
    return types[path.pathExtension.lowercaseString] ?: @"application/octet-stream";
}

- (void)respondToTask:(id<WKURLSchemeTask>)task data:(NSData *)data mimeType:(NSString *)mimeType {
    NSURLResponse *response = [[NSURLResponse alloc]
        initWithURL:task.request.URL
        MIMEType:mimeType
        expectedContentLength:(NSInteger)data.length
        textEncodingName:[mimeType hasPrefix:@"text/"] || [mimeType isEqualToString:@"application/json"] ? @"utf-8" : nil];
    [task didReceiveResponse:response];
    [task didReceiveData:data];
    [task didFinish];
}

- (void)webView:(WKWebView *)webView startURLSchemeTask:(id<WKURLSchemeTask>)urlSchemeTask {
    dispatch_async(dispatch_get_global_queue(QOS_CLASS_USER_INITIATED, 0), ^{
        NSString *path = urlSchemeTask.request.URL.path ?: @"/";
        if ([path hasPrefix:@"/api/"]) {
            NSDictionary *commands = @{
                @"/api/state": @"state",
                @"/api/topics": @"topics",
                @"/api/discover": @"discover",
                @"/api/candidates/action": @"candidate",
                @"/api/candidates/clear": @"clear",
                @"/api/maintenance/rebuild": @"maintenance",
                @"/api/tasks": @"tasks",
                @"/api/backup": @"backup",
            };
            NSString *command = commands[path];
            NSData *data;
            if (command == nil) {
                data = [NSJSONSerialization dataWithJSONObject:@{@"error": @"接口不存在"} options:0 error:nil];
            } else {
                data = [self runBackendCommand:command body:[self requestBody:urlSchemeTask.request]];
            }
            [self respondToTask:urlSchemeTask data:data mimeType:@"application/json"];
            return;
        }

        NSString *relative = [path isEqualToString:@"/"] ? @"index.html" : [path substringFromIndex:1];
        NSURL *webRoot = [[self.projectRoot URLByAppendingPathComponent:@"web"] URLByStandardizingPath];
        NSURL *resource = [[webRoot URLByAppendingPathComponent:relative] URLByStandardizingPath];
        NSString *rootPrefix = [webRoot.path stringByAppendingString:@"/"];
        if (![resource.path hasPrefix:rootPrefix]) {
            NSError *error = [NSError errorWithDomain:@"PaperAtlas" code:403 userInfo:@{NSLocalizedDescriptionKey: @"资源路径无效"}];
            [urlSchemeTask didFailWithError:error];
            return;
        }
        NSData *data = [NSData dataWithContentsOfURL:resource];
        if (data == nil) {
            NSError *error = [NSError errorWithDomain:@"PaperAtlas" code:404 userInfo:@{NSLocalizedDescriptionKey: @"资源不存在"}];
            [urlSchemeTask didFailWithError:error];
            return;
        }
        [self respondToTask:urlSchemeTask data:data mimeType:[self mimeTypeForPath:resource.path]];
    });
}

- (void)webView:(WKWebView *)webView stopURLSchemeTask:(id<WKURLSchemeTask>)urlSchemeTask {
    // The file and command operations are short-lived and safely finish in the background.
}

@end


@interface PaperAtlasDelegate : NSObject <NSApplicationDelegate, WKNavigationDelegate, WKScriptMessageHandler>
@property(nonatomic, strong) NSWindow *window;
@property(nonatomic, strong) WKWebView *webView;
@property(nonatomic, strong) NSView *loadingView;
@property(nonatomic, strong) NSTextField *statusLabel;
@property(nonatomic, strong) NSTask *prepareTask;
@property(nonatomic, strong) NSURL *papersDirectory;
@property(nonatomic, strong) PaperAtlasSchemeHandler *schemeHandler;
@end


@implementation PaperAtlasDelegate

- (NSImage *)bundledApplicationIcon {
    NSString *iconPath = [NSBundle.mainBundle pathForResource:@"AppIcon" ofType:@"png"];
    NSImage *icon = iconPath == nil ? nil : [[NSImage alloc] initWithContentsOfFile:iconPath];
    return icon ?: NSApp.applicationIconImage;
}

- (NSURL *)projectRoot {
    NSArray<NSURL *> *locations = [NSFileManager.defaultManager URLsForDirectory:NSApplicationSupportDirectory
                                                                        inDomains:NSUserDomainMask];
    NSURL *base = locations.firstObject ?: [NSURL fileURLWithPath:[NSHomeDirectory() stringByAppendingPathComponent:@"Library/Application Support"]];
    return [[base URLByAppendingPathComponent:@"Paper Atlas" isDirectory:YES]
        URLByAppendingPathComponent:@"runtime" isDirectory:YES];
}

- (NSURL *)bundledRuntimeRoot {
    return [NSBundle.mainBundle.resourceURL URLByAppendingPathComponent:@"runtime" isDirectory:YES];
}

- (NSURL *)pythonExecutable {
    NSURL *bundled = [NSBundle.mainBundle.resourceURL URLByAppendingPathComponent:@"python/bin/python3"];
    if ([NSFileManager.defaultManager isExecutableFileAtPath:bundled.path]) return bundled;
    return [[[self projectRoot] URLByAppendingPathComponent:@".venv/bin/python"] URLByStandardizingPath];
}

- (BOOL)usesBundledPython {
    NSString *bundledRoot = [NSBundle.mainBundle.resourceURL URLByAppendingPathComponent:@"python"].path;
    return [[[self pythonExecutable] path] hasPrefix:[bundledRoot stringByAppendingString:@"/"]];
}

- (BOOL)copyBundledItem:(NSString *)relative replace:(BOOL)replace error:(NSError **)error {
    NSURL *source = [[self bundledRuntimeRoot] URLByAppendingPathComponent:relative];
    NSURL *destination = [[self projectRoot] URLByAppendingPathComponent:relative];
    NSFileManager *manager = NSFileManager.defaultManager;
    if (![manager fileExistsAtPath:source.path]) return YES;
    if ([manager fileExistsAtPath:destination.path]) {
        if (!replace) return YES;
        if (![manager removeItemAtURL:destination error:error]) return NO;
    }
    if (![manager createDirectoryAtURL:destination.URLByDeletingLastPathComponent
            withIntermediateDirectories:YES attributes:nil error:error]) return NO;
    return [manager copyItemAtURL:source toURL:destination error:error];
}

- (BOOL)installRuntimeFiles:(NSError **)error {
    if (![NSFileManager.defaultManager createDirectoryAtURL:[self projectRoot]
            withIntermediateDirectories:YES attributes:nil error:error]) return NO;
    NSArray<NSString *> *programFiles = @[
        @"scripts", @"requirements.txt", @"VERSION",
        @"web/index.html", @"web/app.js", @"web/styles.css",
    ];
    for (NSString *relative in programFiles) {
        if (![self copyBundledItem:relative replace:YES error:error]) return NO;
    }
    NSArray<NSString *> *initialState = @[
        @"config/discovery.json", @"config/tasks.json",
        @"web/data/graph.json", @"web/data/graph-data.js",
        @"web/data/discovery.json", @"web/data/discovery-data.js",
    ];
    for (NSString *relative in initialState) {
        if (![self copyBundledItem:relative replace:NO error:error]) return NO;
    }
    return YES;
}

- (NSURL *)cacheDirectory {
    return [[self projectRoot] URLByAppendingPathComponent:@".cache" isDirectory:YES];
}

- (void)applicationWillFinishLaunching:(NSNotification *)notification {
    [NSApp setApplicationIconImage:[self bundledApplicationIcon]];
}

- (void)applicationDidFinishLaunching:(NSNotification *)notification {
    [NSApp setApplicationIconImage:[self bundledApplicationIcon]];
    NSError *runtimeError = nil;
    if (![self installRuntimeFiles:&runtimeError]) {
        NSAlert *alert = [[NSAlert alloc] init];
        alert.messageText = @"Paper Atlas 无法准备本地运行目录";
        alert.informativeText = runtimeError.localizedDescription ?: @"请检查 Application Support 目录权限。";
        [alert runModal];
        [NSApp terminate:nil];
        return;
    }
    self.papersDirectory = [self choosePapersDirectoryIfNeeded];
    if (self.papersDirectory == nil) {
        [NSApp terminate:nil];
        return;
    }
    [self buildWindow];
    [NSApp activateIgnoringOtherApps:YES];
    [self prepareEnvironment];
}

- (BOOL)applicationShouldTerminateAfterLastWindowClosed:(NSApplication *)sender {
    return YES;
}

- (void)applicationWillTerminate:(NSNotification *)notification {
    [self.webView.configuration.userContentController removeScriptMessageHandlerForName:@"paperAtlas"];
    if (self.prepareTask.running) [self.prepareTask terminate];
}

- (void)buildWindow {
    self.window = [[NSWindow alloc]
        initWithContentRect:NSMakeRect(0, 0, 1320, 860)
        styleMask:(NSWindowStyleMaskTitled | NSWindowStyleMaskClosable |
                   NSWindowStyleMaskMiniaturizable | NSWindowStyleMaskResizable)
        backing:NSBackingStoreBuffered
        defer:NO];
    self.window.title = @"Paper Atlas";
    self.window.titleVisibility = NSWindowTitleHidden;
    self.window.titlebarAppearsTransparent = YES;
    self.window.movableByWindowBackground = YES;
    self.window.minSize = NSMakeSize(900, 640);
    self.window.backgroundColor = [NSColor colorWithRed:0.94 green:0.96 blue:0.99 alpha:1.0];
    [self.window center];

    WKWebViewConfiguration *configuration = [[WKWebViewConfiguration alloc] init];
    configuration.websiteDataStore = WKWebsiteDataStore.defaultDataStore;
    self.schemeHandler = [[PaperAtlasSchemeHandler alloc]
        initWithProjectRoot:[self projectRoot]
        papersDirectory:self.papersDirectory
        pythonExecutable:[self pythonExecutable]];
    [configuration setURLSchemeHandler:self.schemeHandler forURLScheme:@"paperatlas"];
    [configuration.userContentController addScriptMessageHandler:self name:@"paperAtlas"];
    self.webView = [[WKWebView alloc] initWithFrame:NSZeroRect configuration:configuration];
    self.webView.navigationDelegate = self;
    self.webView.allowsMagnification = YES;
    self.webView.translatesAutoresizingMaskIntoConstraints = NO;
    self.webView.hidden = YES;
    [self.window.contentView addSubview:self.webView];

    self.loadingView = [[NSView alloc] initWithFrame:NSZeroRect];
    self.loadingView.translatesAutoresizingMaskIntoConstraints = NO;
    [self.window.contentView addSubview:self.loadingView];

    NSImageView *icon = [[NSImageView alloc] initWithFrame:NSZeroRect];
    icon.image = [self bundledApplicationIcon];
    icon.imageScaling = NSImageScaleProportionallyUpOrDown;
    [icon.widthAnchor constraintEqualToConstant:92].active = YES;
    [icon.heightAnchor constraintEqualToConstant:92].active = YES;

    NSTextField *title = [NSTextField labelWithString:@"Paper Atlas"];
    title.font = [NSFont systemFontOfSize:28 weight:NSFontWeightSemibold];
    title.alignment = NSTextAlignmentCenter;

    self.statusLabel = [NSTextField labelWithString:@"正在准备论文图谱…"];
    self.statusLabel.font = [NSFont systemFontOfSize:15];
    self.statusLabel.textColor = NSColor.secondaryLabelColor;
    self.statusLabel.alignment = NSTextAlignmentCenter;
    self.statusLabel.maximumNumberOfLines = 2;

    NSProgressIndicator *progress = [[NSProgressIndicator alloc] initWithFrame:NSZeroRect];
    progress.style = NSProgressIndicatorStyleSpinning;
    progress.controlSize = NSControlSizeSmall;
    [progress startAnimation:nil];

    NSStackView *loadingStack = [NSStackView stackViewWithViews:@[icon, title, self.statusLabel, progress]];
    loadingStack.orientation = NSUserInterfaceLayoutOrientationVertical;
    loadingStack.spacing = 15;
    loadingStack.alignment = NSLayoutAttributeCenterX;
    loadingStack.translatesAutoresizingMaskIntoConstraints = NO;
    [self.loadingView addSubview:loadingStack];

    [NSLayoutConstraint activateConstraints:@[
        [self.webView.leadingAnchor constraintEqualToAnchor:self.window.contentView.leadingAnchor],
        [self.webView.trailingAnchor constraintEqualToAnchor:self.window.contentView.trailingAnchor],
        [self.webView.topAnchor constraintEqualToAnchor:self.window.contentView.topAnchor],
        [self.webView.bottomAnchor constraintEqualToAnchor:self.window.contentView.bottomAnchor],
        [self.loadingView.leadingAnchor constraintEqualToAnchor:self.window.contentView.leadingAnchor],
        [self.loadingView.trailingAnchor constraintEqualToAnchor:self.window.contentView.trailingAnchor],
        [self.loadingView.topAnchor constraintEqualToAnchor:self.window.contentView.topAnchor],
        [self.loadingView.bottomAnchor constraintEqualToAnchor:self.window.contentView.bottomAnchor],
        [loadingStack.centerXAnchor constraintEqualToAnchor:self.loadingView.centerXAnchor],
        [loadingStack.centerYAnchor constraintEqualToAnchor:self.loadingView.centerYAnchor],
        [self.statusLabel.widthAnchor constraintEqualToConstant:360],
    ]];
    [self.window makeKeyAndOrderFront:nil];
}

- (NSURL *)choosePapersDirectoryIfNeeded {
    NSUserDefaults *defaults = NSUserDefaults.standardUserDefaults;
    NSString *storedPath = [defaults stringForKey:@"papersDirectory"];
    if (storedPath == nil) {
        NSUserDefaults *legacyDefaults = [[NSUserDefaults alloc] initWithSuiteName:@"local.paper-atlas.desktop"];
        storedPath = [legacyDefaults stringForKey:@"papersDirectory"];
        if (storedPath != nil) [defaults setObject:storedPath forKey:@"papersDirectory"];
    }
    NSString *launcherPath = [[[self projectRoot] URLByAppendingPathComponent:@"scripts/app_backend.py"] path];
    if (storedPath != nil && [NSFileManager.defaultManager isReadableFileAtPath:launcherPath] &&
        [NSFileManager.defaultManager fileExistsAtPath:storedPath]) {
        return [NSURL fileURLWithPath:storedPath isDirectory:YES];
    }

    NSOpenPanel *panel = [NSOpenPanel openPanel];
    panel.title = @"选择 Paper Atlas 论文库";
    panel.message = @"请选择用于保存 10 个分类目录和论文 PDF 的文件夹。首次选择用于授予 macOS 访问权限。";
    panel.prompt = @"选择论文库";
    panel.canChooseDirectories = YES;
    panel.canChooseFiles = NO;
    panel.allowsMultipleSelection = NO;
    panel.directoryURL = [NSURL fileURLWithPath:[NSHomeDirectory() stringByAppendingPathComponent:@"Downloads/paper"] isDirectory:YES];
    if ([panel runModal] != NSModalResponseOK || panel.URL == nil) return nil;
    [defaults setObject:panel.URL.path forKey:@"papersDirectory"];
    return panel.URL;
}

- (void)prepareEnvironment {
    NSError *error = nil;
    [NSFileManager.defaultManager createDirectoryAtURL:[self cacheDirectory]
                           withIntermediateDirectories:YES attributes:nil error:&error];
    NSURL *logURL = [[self cacheDirectory] URLByAppendingPathComponent:@"paper-atlas-app.log"];
    if (![NSFileManager.defaultManager fileExistsAtPath:logURL.path]) {
        [NSFileManager.defaultManager createFileAtPath:logURL.path contents:nil attributes:nil];
    }
    NSFileHandle *logHandle = [NSFileHandle fileHandleForWritingAtPath:logURL.path];
    [logHandle seekToEndOfFile];

    NSTask *task = [[NSTask alloc] init];
    task.executableURL = [self usesBundledPython]
        ? [self pythonExecutable]
        : [NSURL fileURLWithPath:@"/usr/bin/python3"];
    task.arguments = @[
        [[[self projectRoot] URLByAppendingPathComponent:@"scripts/app_backend.py"] path],
        @"prepare", @"--papers-dir", self.papersDirectory.path,
    ];
    task.currentDirectoryURL = [self projectRoot];
    if ([self usesBundledPython]) {
        NSMutableDictionary *environment = [NSProcessInfo.processInfo.environment mutableCopy];
        environment[@"PAPER_ATLAS_USE_CURRENT_PYTHON"] = @"1";
        environment[@"PYTHONDONTWRITEBYTECODE"] = @"1";
        environment[@"PYTHONNOUSERSITE"] = @"1";
        environment[@"SSL_CERT_FILE"] = @"/etc/ssl/cert.pem";
        task.environment = environment;
    }
    task.standardOutput = logHandle;
    task.standardError = logHandle;
    __weak PaperAtlasDelegate *weakSelf = self;
    task.terminationHandler = ^(NSTask *completed) {
        dispatch_async(dispatch_get_main_queue(), ^{
            PaperAtlasDelegate *strongSelf = weakSelf;
            if (strongSelf == nil) return;
            if (completed.terminationStatus != 0) {
                [strongSelf showFailure:@"应用环境准备失败，请查看 .cache/paper-atlas-app.log"];
                return;
            }
            strongSelf.statusLabel.stringValue = @"正在载入论文关系图谱…";
            NSURL *url = [NSURL URLWithString:@"paperatlas://app/index.html"];
            [strongSelf.webView loadRequest:[NSURLRequest requestWithURL:url]];
        });
    };
    if (![task launchAndReturnError:&error]) {
        [self showFailure:[NSString stringWithFormat:@"无法启动应用：%@", error.localizedDescription]];
        return;
    }
    self.prepareTask = task;
}

- (void)webView:(WKWebView *)webView didFinishNavigation:(WKNavigation *)navigation {
    self.webView.hidden = NO;
    self.loadingView.hidden = YES;
    [self.window makeFirstResponder:self.webView];
}

- (void)userContentController:(WKUserContentController *)userContentController
      didReceiveScriptMessage:(WKScriptMessage *)message {
    if (![message.name isEqualToString:@"paperAtlas"] || ![message.body isKindOfClass:NSDictionary.class]) return;
    NSDictionary *request = (NSDictionary *)message.body;
    NSString *identifier = [request[@"id"] isKindOfClass:NSString.class] ? request[@"id"] : @"";
    NSString *path = [request[@"path"] isKindOfClass:NSString.class] ? request[@"path"] : @"";
    NSString *bodyText = [request[@"body"] isKindOfClass:NSString.class] ? request[@"body"] : @"";
    NSDictionary *commands = @{
        @"/api/state": @"state",
        @"/api/topics": @"topics",
        @"/api/discover": @"discover",
        @"/api/candidates/action": @"candidate",
        @"/api/candidates/clear": @"clear",
        @"/api/maintenance/rebuild": @"maintenance",
        @"/api/tasks": @"tasks",
        @"/api/backup": @"backup",
    };
    NSString *command = commands[path];
    if (identifier.length == 0) return;

    __weak PaperAtlasDelegate *weakSelf = self;
    dispatch_async(dispatch_get_global_queue(QOS_CLASS_USER_INITIATED, 0), ^{
        PaperAtlasDelegate *strongSelf = weakSelf;
        if (strongSelf == nil) return;
        NSData *result;
        if (command == nil) {
            result = [NSJSONSerialization dataWithJSONObject:@{@"error": @"应用接口不存在"} options:0 error:nil];
        } else {
            @synchronized (strongSelf.schemeHandler) {
                result = [strongSelf.schemeHandler runBackendCommand:command
                    body:[bodyText dataUsingEncoding:NSUTF8StringEncoding]];
            }
        }
        NSISO8601DateFormatter *dateFormatter = [[NSISO8601DateFormatter alloc] init];
        NSDictionary *bridgeStatus = @{
            @"command": command ?: @"unknown",
            @"completed": @YES,
            @"updated_at": [dateFormatter stringFromDate:[NSDate date]],
        };
        NSData *bridgeData = [NSJSONSerialization dataWithJSONObject:bridgeStatus options:0 error:nil];
        NSURL *bridgeURL = [[strongSelf cacheDirectory] URLByAppendingPathComponent:@"paper-atlas-native-bridge.json"];
        [bridgeData writeToURL:bridgeURL atomically:YES];
        NSString *encoded = [result base64EncodedStringWithOptions:0];
        NSData *argumentsData = [NSJSONSerialization dataWithJSONObject:@[identifier, encoded] options:0 error:nil];
        NSString *arguments = [[NSString alloc] initWithData:argumentsData encoding:NSUTF8StringEncoding];
        dispatch_async(dispatch_get_main_queue(), ^{
            NSString *script = [NSString stringWithFormat:@"window.__paperAtlasNativeResolve.apply(null, %@)", arguments];
            [strongSelf.webView evaluateJavaScript:script completionHandler:^(id value, NSError *error) {
                NSMutableDictionary *deliveryStatus = [bridgeStatus mutableCopy];
                deliveryStatus[@"delivered"] = @(error == nil);
                if (error != nil) deliveryStatus[@"delivery_error"] = error.localizedDescription;
                NSData *deliveryData = [NSJSONSerialization dataWithJSONObject:deliveryStatus options:0 error:nil];
                [deliveryData writeToURL:bridgeURL atomically:YES];
            }];
        });
    });
}

- (void)webView:(WKWebView *)webView
    decidePolicyForNavigationAction:(WKNavigationAction *)navigationAction
    decisionHandler:(void (^)(WKNavigationActionPolicy))decisionHandler {
    NSURL *url = navigationAction.request.URL;
    if (url == nil) {
        decisionHandler(WKNavigationActionPolicyCancel);
        return;
    }

    BOOL isApp = [url.scheme.lowercaseString isEqualToString:@"paperatlas"];
    if (isApp && [url.path hasPrefix:@"/papers/"] && navigationAction.targetFrame == nil) {
        NSString *relative = [[url.path substringFromIndex:@"/papers/".length] stringByRemovingPercentEncoding];
        NSURL *paperURL = [self.papersDirectory URLByAppendingPathComponent:relative];
        NSString *root = self.papersDirectory.URLByStandardizingPath.path;
        NSString *paper = paperURL.URLByStandardizingPath.path;
        if ([paper hasPrefix:[root stringByAppendingString:@"/"]] && [paper.pathExtension.lowercaseString isEqualToString:@"pdf"]) {
            [NSWorkspace.sharedWorkspace openURL:[NSURL fileURLWithPath:paper]];
        }
        decisionHandler(WKNavigationActionPolicyCancel);
        return;
    }

    if (!isApp && [@[@"http", @"https"] containsObject:url.scheme.lowercaseString] &&
        (navigationAction.navigationType == WKNavigationTypeLinkActivated || navigationAction.targetFrame == nil)) {
        [NSWorkspace.sharedWorkspace openURL:url];
        decisionHandler(WKNavigationActionPolicyCancel);
        return;
    }
    decisionHandler(WKNavigationActionPolicyAllow);
}

- (void)webView:(WKWebView *)webView didFailNavigation:(WKNavigation *)navigation withError:(NSError *)error {
    [self showFailure:[NSString stringWithFormat:@"图谱载入失败：%@", error.localizedDescription]];
}

- (void)showFailure:(NSString *)message {
    self.loadingView.hidden = NO;
    self.webView.hidden = YES;
    self.statusLabel.stringValue = message;
    self.statusLabel.textColor = NSColor.systemRedColor;
}

@end


int main(int argc, const char *argv[]) {
    @autoreleasepool {
        NSApplication *application = NSApplication.sharedApplication;
        [application setActivationPolicy:NSApplicationActivationPolicyRegular];
        [NSProcessInfo.processInfo setProcessName:@"Paper Atlas"];
        NSString *iconPath = [NSBundle.mainBundle pathForResource:@"AppIcon" ofType:@"png"];
        NSImage *icon = iconPath == nil ? nil : [[NSImage alloc] initWithContentsOfFile:iconPath];
        if (icon != nil) [application setApplicationIconImage:icon];
        PaperAtlasDelegate *delegate = [[PaperAtlasDelegate alloc] init];
        application.delegate = delegate;
        [application run];
    }
    return 0;
}
