import re
import json
import csv
import argparse
from pathlib import Path

# 匹配 "<任意用户名> 2026年3月9日 08:36" 格式的行
HEADER_RE = re.compile(r"^\S+\s+(\d{4})年(\d{1,2})月(\d{1,2})日\s+(\d{2}:\d{2})")


def parse_records(input_file):
    entries = []
    current_time = None
    current_lines = []

    with open(input_file, encoding="utf-8") as f:
        for line in f:
            line = line.rstrip("\n")
            m = HEADER_RE.match(line)
            if m:
                if current_time is not None:
                    message = "\n".join(current_lines).strip()
                    if message:
                        entries.append({"time": current_time, "message": message})
                year, month, day, hm = m.group(1), m.group(2), m.group(3), m.group(4)
                current_time = f"{year}/{int(month):02d}/{int(day):02d} {hm}"
                current_lines = []
            else:
                if current_time is not None:
                    current_lines.append(line)

    if current_time is not None:
        message = "\n".join(current_lines).strip()
        if message:
            entries.append({"time": current_time, "message": message})

    return entries


def write_jsonl(entries, output_file):
    with open(output_file, "w", encoding="utf-8") as f:
        for entry in entries:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def write_csv(entries, output_file):
    with open(output_file, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["时间", "消息内容"])
        for entry in entries:
            writer.writerow([entry["time"], entry["message"]])


def convert_file(input_path, output_path, fmt):
    entries = parse_records(input_path)
    if fmt == "jsonl":
        write_jsonl(entries, output_path)
    else:
        write_csv(entries, output_path)
    return len(entries)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="将飞书聊天记录转换为结构化格式")
    parser.add_argument("--input", default=None, help="输入文件路径（单文件模式）")
    parser.add_argument("--output", default=None, help="输出文件路径（单文件模式，默认同名替换后缀）")
    parser.add_argument("--input-dir", default="raw", help="输入文件夹路径（批量模式）")
    parser.add_argument("--output-dir", default="json", help="输出文件夹路径（批量模式）")
    parser.add_argument("--format", choices=["jsonl", "csv"], default="jsonl", help="输出格式（默认 jsonl）")
    args = parser.parse_args()

    if args.input_dir:
        # 批量模式
        input_dir = Path(args.input_dir)
        output_dir = Path(args.output_dir) if args.output_dir else input_dir.parent / "json"
        output_dir.mkdir(parents=True, exist_ok=True)

        txt_files = sorted(input_dir.glob("*.txt"))
        if not txt_files:
            print(f"在 {input_dir} 中未找到 .txt 文件")
        else:
            total = 0
            for txt_file in txt_files:
                out_file = output_dir / txt_file.with_suffix(f".{args.format}").name
                count = convert_file(txt_file, out_file, args.format)
                print(f"  {txt_file.name} → {out_file.name}  ({count} 条)")
                total += count
            print(f"\n批量转换完成，共 {len(txt_files)} 个文件，{total} 条记录，已保存到 {output_dir}/")
    else:
        # 单文件模式
        input_file = args.input or "record.txt"
        output_file = args.output or str(Path(input_file).with_suffix(f".{args.format}"))
        count = convert_file(input_file, output_file, args.format)
        print(f"转换完成，共 {count} 条记录，已保存到 {output_file}")
