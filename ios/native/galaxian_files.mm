// Native Files picker only. Archive parsing remains in upstream GDScript.
#import <UIKit/UIKit.h>
#import <UniformTypeIdentifiers/UniformTypeIdentifiers.h>
#include "core/config/engine.h"
#include "core/object/class_db.h"

class GalaxianFiles;
static GalaxianFiles *plugin = nullptr;
@interface GalaxianDocumentDelegate : NSObject <UIDocumentPickerDelegate>
@end
static GalaxianDocumentDelegate *delegate;

class GalaxianFiles : public Object {
    GDCLASS(GalaxianFiles, Object);
    bool pending = false;
    Dictionary result;
    NSString *temporary_directory = nil;
protected:
    static void _bind_methods() {
        ClassDB::bind_method(D_METHOD("choose"), &GalaxianFiles::choose);
        ClassDB::bind_method(D_METHOD("is_pending"), &GalaxianFiles::is_pending);
        ClassDB::bind_method(D_METHOD("take_result"), &GalaxianFiles::take_result);
        ClassDB::bind_method(D_METHOD("clear_import"), &GalaxianFiles::clear_import);
    }
public:
    void clear_import() {
        if (temporary_directory) {
            [NSFileManager.defaultManager removeItemAtPath:temporary_directory error:nil];
            temporary_directory = nil;
        }
    }
    bool is_pending() const { return pending; }
    Dictionary take_result() { Dictionary value = result; result = Dictionary(); return value; }
    void fail(const char *message) { result["error"] = String::utf8(message); pending = false; }
    void cancel() { result["cancelled"] = true; pending = false; }
    void selected(NSURL *url) {
        // asCopy:YES gives us a sandbox-local file. Move it out of the picker inbox
        // before returning to Godot, and retain it through asynchronous extraction.
        NSNumber *regular = nil, *size = nil;
        NSError *error = nil;
        if (![url getResourceValue:&regular forKey:NSURLIsRegularFileKey error:&error] ||
            !regular.boolValue || ![url getResourceValue:&size forKey:NSURLFileSizeKey error:&error] ||
            size.unsignedLongLongValue > 128ULL * 1024 * 1024) {
            fail("Choose a regular Galaxy on Fire IPA under 128 MiB.");
            return;
        }
        temporary_directory = [NSTemporaryDirectory() stringByAppendingPathComponent:
            [@"galaxian-import-" stringByAppendingString:NSUUID.UUID.UUIDString]];
        if (![NSFileManager.defaultManager createDirectoryAtPath:temporary_directory
                withIntermediateDirectories:NO attributes:nil error:&error]) {
            clear_import(); fail("Could not create temporary import storage."); return;
        }
        NSString *path = [temporary_directory stringByAppendingPathComponent:@"game.ipa"];
        if (![NSFileManager.defaultManager moveItemAtURL:url toURL:[NSURL fileURLWithPath:path] error:&error]) {
            clear_import(); fail("Could not prepare the selected IPA. Download it in Files and try again."); return;
        }
        result["path"] = String::utf8(path.UTF8String);
        pending = false;
    }
    void choose() {
        if (pending) { return; }
        clear_import(); result = Dictionary();
        UIViewController *presenter = nil;
        for (UIScene *scene in UIApplication.sharedApplication.connectedScenes) {
            if (scene.activationState != UISceneActivationStateForegroundActive ||
                ![scene isKindOfClass:UIWindowScene.class]) { continue; }
            for (UIWindow *window in ((UIWindowScene *)scene).windows) {
                if (window.isKeyWindow) { presenter = window.rootViewController; break; }
            }
            if (presenter) { break; }
        }
        while (presenter.presentedViewController) { presenter = presenter.presentedViewController; }
        if (!presenter || presenter.isBeingDismissed) {
            fail("The file picker cannot open right now. Please try again."); return;
        }
        // Providers do not consistently classify .ipa files; the existing importer
        // validates the contents instead of trusting a filename or MIME type.
        UIDocumentPickerViewController *picker = [[UIDocumentPickerViewController alloc]
            initForOpeningContentTypes:@[UTTypeData] asCopy:YES];
        picker.allowsMultipleSelection = NO;
        picker.delegate = delegate;
        pending = true;
        [presenter presentViewController:picker animated:YES completion:nil];
    }
    ~GalaxianFiles() { clear_import(); }
};

@implementation GalaxianDocumentDelegate
- (void)documentPicker:(UIDocumentPickerViewController *)controller didPickDocumentsAtURLs:(NSArray<NSURL *> *)urls {
    if (!plugin) { return; }
    if (urls.count) { plugin->selected(urls.firstObject); } else { plugin->cancel(); }
}
- (void)documentPickerWasCancelled:(UIDocumentPickerViewController *)controller {
    if (plugin) { plugin->cancel(); }
}
@end

void galaxian_files_init() {
    ClassDB::register_class<GalaxianFiles>();
    plugin = memnew(GalaxianFiles);
    delegate = [GalaxianDocumentDelegate new];
    Engine::get_singleton()->add_singleton(Engine::Singleton("GalaxianFiles", plugin));
}
void galaxian_files_deinit() {
    Engine::get_singleton()->remove_singleton("GalaxianFiles");
    memdelete(plugin); plugin = nullptr; delegate = nil;
}
