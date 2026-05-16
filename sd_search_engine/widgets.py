class LogAnalyzerWidget:
    def __init__(self, results):
        self.results = results
    
    def activate(self):
        log_count = len(self.results)
        print(f"\n[Widget] Analyze Logs - Found {log_count} log files")
        print("  Commands: --tail, --grep PATTERN, --errors-only")


class GalleryViewWidget:
    def __init__(self, results):
        self.results = results
    
    def activate(self):
        image_count = len(self.results)
        print(f"\n[Widget] View as Gallery - Found {image_count} images")
        print("  Commands: --slideshow, --thumbnails SIZE")


class ColorPaletteWidget:
    def __init__(self, results):
        self.results = results
    
    def activate(self):
        colors_found = set()
        for result in self.results:
            filepath, filename, extension, preview = result
            if "Dominant color:" in preview:
                color_name = preview.split("Dominant color: ")[1]
                colors_found.add(color_name)
        
        if colors_found:
            print(f"\n[Widget] Color Palette - Found colors: {', '.join(sorted(colors_found))}")
            print("  Commands: --group-by-color, --color-distribution")


class CodeHighlightWidget:
    def __init__(self, results):
        self.results = results
    
    def activate(self):
        code_count = len(self.results)
        print(f"\n[Widget] Code Highlight - Found {code_count} source files")
        print("  Commands: --syntax-check, --line-count")


class FileStatsWidget:
    def __init__(self, results):
        self.results = results
    
    def activate(self):
        result_count = len(self.results)
        extensions = {}
        for result in self.results:
            filepath, filename, extension, preview = result
            extensions[extension] = extensions.get(extension, 0) + 1
        
        top_ext = max(extensions.items(), key=lambda x: x[1])[0] if extensions else "unknown"
        print(f"\n[Widget] File Stats - {result_count} files, Top type: {top_ext}")
        print(f"  Types: {', '.join(f'{k}({v})' for k, v in sorted(extensions.items(), key=lambda x: -x[1])[:3])}")


class WidgetFactory:
    def get_widgets(self, results, parsed_query):
        if not results:
            return []
        
        widgets = []
        
        # Analyze file types
        extensions = {}
        for result in results:
            filepath, filename, extension, preview = result
            extensions[extension] = extensions.get(extension, 0) + 1
        
        # Check for logs
        log_count = extensions.get(".log", 0)
        if log_count > 0 and log_count / len(results) > 0.3:
            widgets.append(LogAnalyzerWidget(results))
        
        # Check for images
        image_exts = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp"}
        image_count = sum(extensions.get(ext, 0) for ext in image_exts)
        if image_count > 0 and image_count / len(results) > 0.3:
            widgets.append(GalleryViewWidget(results))
        
        # Check for color queries
        if parsed_query.get("color_terms"):
            widgets.append(ColorPaletteWidget(results))
        
        # Check for code files
        code_exts = {".py", ".js", ".java", ".cpp", ".c", ".go", ".rs", ".rb"}
        code_count = sum(extensions.get(ext, 0) for ext in code_exts)
        if code_count > 0 and code_count / len(results) > 0.3:
            widgets.append(CodeHighlightWidget(results))
        
        # Always show file stats if multiple types
        if len(extensions) > 1 or len(results) > 3:
            widgets.append(FileStatsWidget(results))
        
        return widgets
