#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
生成「只跳过 ReadRecord 的 CRC 校验」的补丁 so。
仅 NOP 两处: 0x19A8030 (cmp x0,x19) 和 0x19A8038 (b.ne)。
Decode/Encode/CRC 计算全部保留 -> 游戏读档接受任意 CRC，但重存时会写出带正确 CRC 的标准存档。
用法:
  python make_crc_patch.py --so tools/libil2cpp.so --out tools/libil2cpp_crconly.so
注意: libil2cpp.so 的「文件偏移 == 虚拟地址」(相关 LOAD 段)，所以直接用地址。
"""
import argparse, hashlib

NOP = bytes([0xD5, 0x03, 0x20, 0x1F])
PATCHES = [0x19A8030, 0x19A8038]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--so", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    data = bytearray(open(args.so, "rb").read())
    print(f"原版 so md5: {hashlib.md5(data).hexdigest()}")
    for a in PATCHES:
        if a + 4 > len(data):
            raise SystemExit(f"[!] 偏移越界: {a:#x}")
        orig = bytes(data[a:a + 4])
        data[a:a + 4] = NOP
        print(f"  0x{a:08x}: {orig.hex()} -> NOP ({NOP.hex()})")
    open(args.out, "wb").write(data)
    print(f"已写出补丁 so: {args.out}  md5: {hashlib.md5(data).hexdigest()}")
    print("记得把原版备份到 /data/local/tmp/libil2cpp.orig.so 以便还原。")


if __name__ == "__main__":
    main()
