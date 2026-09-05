"""Shared template processing logic used by bootstrap.py and bootstrap_ado.py."""
import os
import shutil


def process_templates(source_dir, target_dir, mappings):
    """Recursively processes template files, replacing ${{ values.* }} placeholders."""
    normalized_source = os.path.normpath(source_dir)
    print(f"Starting template generation from: {normalized_source}")

    if not os.path.exists(normalized_source):
        print(f"ERROR: Source template directory '{normalized_source}' does not exist!")
        return

    for root, _dirs, files in os.walk(normalized_source):
        relative_path = os.path.relpath(root, normalized_source)
        dest_root = target_dir if relative_path == "." else os.path.join(target_dir, relative_path)
        os.makedirs(dest_root, exist_ok=True)

        for file_name in files:
            if file_name == "catalog-info.yaml":
                continue
            src_path = os.path.join(root, file_name)
            dst_path = os.path.join(dest_root, file_name)
            print(f"Processing: {os.path.join(relative_path, file_name)}")
            try:
                with open(src_path, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                for placeholder, value in mappings.items():
                    content = content.replace(placeholder, value)
                with open(dst_path, "w", encoding="utf-8") as f:
                    f.write(content)
            except Exception:
                shutil.copy2(src_path, dst_path)

    print("Template generation completed successfully!")
