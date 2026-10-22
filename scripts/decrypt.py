#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
解密某个存档并打印关键字段，同时自检解密是否正确。
用法:
  python decrypt.py --save path/to/save --global-metadata path/to/global-metadata.dat
字段(解密后明文偏移):
  0..3    恒为 0 (自检)
  1912    金币 (int32 大端, 值 = 游戏内金币/10)
  15510/15512/15514/15516  四个资源 (int16 大端)
"""
import argparse

KS = bytes.fromhex(
    "65b648ad7a082f13fdaa4be9c6fb7142b7491e48f1d73908aa32baca1b27f2b5b4c0adb69e7a5d2518906564"
)
MONEY_OFF = 1912
RES_OFFS = [15510, 15512, 15514, 15516]
RES_NAMES = ["心(资源①)", "灯泡(资源②)", "奖杯(资源③)", "第4项(资源④)"]


def load_ks(gm_path, offset=0x30DA18):
    if not gm_path:
        return KS
    with open(gm_path, "rb") as f:
        d = f.read()
    k = d[offset: offset + 44]
    if len(k) != 44:
        raise SystemExit("[!] 密钥流读取失败")
    return k


def decrypt(enc, ks):
    return bytes(enc[i] ^ ks[i % 44] for i in range(len(enc)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--save", required=True)
    ap.add_argument("--global-metadata", help="global-metadata.dat 路径(缺省用内置常量)")
    ap.add_argument("--offset", type=lambda x: int(x, 0), default=0x30DA18)
    args = ap.parse_args()

    ks = load_ks(args.global_metadata, args.offset)
    raw = open(args.save, "rb").read()
    plain = decrypt(raw, ks)

    print(f"文件: {args.save}  密文长度: {len(raw)}")
    print(f"解密前4字节: {plain[0:4].hex()}  (应 = 00000000)")
    if plain[0:4] != b"\x00\x00\x00\x00":
        print("[!] 解密自检失败：前4字节非0，密钥流或文件可能不对")
        return

    print(f"头部CRC(密文4..8): {raw[4:8].hex()}  (算法未公开，无需离线重算)")

    if len(plain) >= MONEY_OFF + 4:
        m = int.from_bytes(plain[MONEY_OFF:MONEY_OFF + 4], "big")
        print(f"\n金币 @ {MONEY_OFF} (int32 大端) = {m}  -> 游戏内金币 = {m*10:,} G")

    print("\n四个资源 (int16 大端):")
    for name, off in zip(RES_NAMES, RES_OFFS):
        if len(plain) >= off + 2:
            v = int.from_bytes(plain[off:off + 2], "big")
            cap = 9999 if off in (15510, 15512) else 999
            flag = "  (已达显示上限)" if v >= cap else ""
            print(f"  {name:14s} @ {off} = {v}{flag}")


if __name__ == "__main__":
    main()
