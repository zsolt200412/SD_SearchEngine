from pathlib import Path
from dataclasses import dataclass
from typing import Dict


@dataclass
class ProcessedFileData:
    filepath: str
    filename: str
    extension: str
    content: str
    preview: str
    file_type: str
    metadata: Dict = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class TextFileProcessor:
    def __init__(self, text_extensions):
        self.text_extensions = text_extensions

    def can_process(self, file_path):
        return file_path.suffix.lower() in self.text_extensions

    def process(self, file_path):
        content = ""
        preview = ""

        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
                preview = content[:50]
        except Exception as e:
            raise Exception(f"Could not read text file {file_path}: {e}")

        return ProcessedFileData(
            filepath=str(file_path),
            filename=file_path.name,
            extension=file_path.suffix,
            content=content,
            preview=preview,
            file_type="text",
            metadata={},
        )


class ImageFileProcessor:
    def __init__(self, image_extensions):
        self.image_extensions = image_extensions

    def can_process(self, file_path):
        return file_path.suffix.lower() in self.image_extensions

    def process(self, file_path):
        from .color_extractor import extract_dominant_color

        try:
            color_data = extract_dominant_color(file_path)
            preview = f"Image - Dominant color: {color_data['dominant_color_name']}"

            return ProcessedFileData(
                filepath=str(file_path),
                filename=file_path.name,
                extension=file_path.suffix,
                content="",
                preview=preview,
                file_type="image",
                metadata={
                    "dominant_color": color_data["dominant_color"],
                    "dominant_color_name": color_data["dominant_color_name"],
                    "dominant_color_hex": color_data["dominant_color_hex"],
                    "color_palette": color_data["color_palette"],
                },
            )
        except Exception as e:
            raise Exception(f"Could not process image file {file_path}: {e}")


class FileProcessorFactory:
    def __init__(self):
        self.processors = []

    def register_processor(self, processor):
        self.processors.append(processor)

    def get_processor(self, file_path):
        for processor in self.processors:
            if processor.can_process(file_path):
                return processor
        return None

    def process_file(self, file_path):
        processor = self.get_processor(file_path)
        if processor is None:
            return None
        return processor.process(file_path)
