#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
从 global-metadata.dat @ 0x30da18 读出 44 字节 XOR 密钥流。
用法:
  python extract_keystream.py --global-metadata path/to/global-metadata.dat
可选:
  --save path/to/save   顺便验证：存档密文前4字节应等于密钥流前4字节
  --offset 0x30da18     自定义密钥流偏移（默认 0x30da18）
"""
import argparse, sys

DEFAULT_OFF = 0x30DA18
DEFAULT_KS = bytes.fromhex(
    "65b648ad7a082f13fdaa4be9c6fb7142b7491e48f1d73908aa32baca1b27f2b5b4c0adb69e7a5d2518906564"
)


def read_keystream(gm_path, offset):
    with open(gm_path, "rb") as f:
        data = f.read()
    if offset + 44 > len(data):
        raise SystemExit(f"[!] global-metadata.dat 太小或偏移不对: len={len(data)} offset={offset:#x}")
    return data[offset: offset + 44]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--global-metadata", help="global-metadata.dat 路径")
    ap.add_argument("--offset", default=hex(DEFAULT_OFF), help=f"密钥流偏移 (默认 {DEFAULT_OFF:#x})")
    ap.add_argument("--save", help="可选：一个存档文件，用于验证密文前4字节==密钥流前4字节")
    args = ap.parse_args()

    off = int(args.offset, 0) if isinstance(args.offset, str) else args.offset

    if args.global_metadata:
        ks = read_keystream(args.global_metadata, off)
        print(f"密钥流 @ {off:#x} ({len(ks)} 字节):")
        print("  " + ks.hex())
    else:
        ks = DEFAULT_KS
        print("未提供 global-metadata.dat，使用内置已验证常量:")
        print("  " + ks.hex())

    if args.save:
        raw = open(args.save, "rb").read()
        enc4 = raw[0:4]
        print(f"\n存档 {args.save} 前4字节密文: {enc4.hex()}")
        print(f"密钥流前4字节          : {ks[0:4].hex()}")
        print("验证:", "OK (密文前4==密钥流前4，说明密钥流正确)" if enc4 == ks[0:4]
              else "不匹配！密钥流可能不对或不是该游戏存档")


if __name__ == "__main__":
    main()
