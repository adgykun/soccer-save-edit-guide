#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
版本变动时，校验/重新定位字段偏移。
用法 A (自检已知偏移):
  python locate_fields.py --save rs/0002 --global-metadata tools/global-metadata.dat
用法 B (差分定位某个资源):
  游戏内把某资源 +1 -> 存一次档 -> 和改名前那份对比
  python locate_fields.py --save-a rs/before --save-b rs/after --global-metadata tools/global-metadata.dat
  会列出「解密文中唯一变化的 int16/int32 大端位置」，极大概率就是该字段。
"""
import argparse

KS = bytes.fromhex(
    "65b648ad7a082f13fdaa4be9c6fb7142b7491e48f1d73908aa32baca1b27f2b5b4c0adb69e7a5d2518906564"
)
MONEY_OFF = 1912
RES_OFFS = [15510, 15512, 15514, 15516]


def load_ks(gm_path, offset=0x30DA18):
    if not gm_path:
        return KS
    with open(gm_path, "rb") as f:
        d = f.read()
    return d[offset: offset + 44]


def decrypt(enc, ks):
    return bytes(enc[i] ^ ks[i % 44] for i in range(len(enc)))


def int16_be_at(b, off):
    return int.from_bytes(b[off:off + 2], "big")


def int32_be_at(b, off):
    return int.from_bytes(b[off:off + 4], "big")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--save")
    ap.add_argument("--save-a", help="改动前存档")
    ap.add_argument("--save-b", help="改动后存档")
    ap.add_argument("--global-metadata")
    args = ap.parse_args()

    ks = load_ks(args.global_metadata)

    if args.save_a and args.save_b:
        pa = decrypt(open(args.save_a, "rb").read(), ks)
        pb = decrypt(open(args.save_b, "rb").read(), ks)
        if pa[0:4] != b"\x00\x00\x00\x00" or pb[0:4] != b"\x00\x00\x00\x00":
            raise SystemExit("[!] 解密自检失败：前4字节非0")
        n = min(len(pa), len(pb))
        diffs = [i for i in range(n) if pa[i] != pb[i]]
        print(f"差异字节数: {len(diffs)}")
        if diffs:
            lo, hi = min(diffs), max(diffs)
            print(f"差异区间: [{lo}:{hi+1}]")
            print("候选 int16 大端 (在差异区间内且变化):")
            for off in range(max(0, lo - 3), min(n - 1, hi + 1)):
                if int16_be_at(pa, off) != int16_be_at(pb, off):
                    print(f"  off {off}: {int16_be_at(pa,off)} -> {int16_be_at(pb,off)}")
            print("候选 int32 大端:")
            for off in range(max(0, lo - 3), min(n - 3, hi + 1)):
                if int32_be_at(pa, off) != int32_be_at(pb, off):
                    print(f"  off {off}: {int32_be_at(pa,off)} -> {int32_be_at(pb,off)}")
        return

    if args.save:
        raw = open(args.save, "rb").read()
        p = decrypt(raw, ks)
        print(f"前4字节: {p[0:4].hex()} (应=00000000)")
        if p[0:4] != b"\x00\x00\x00\x00":
            print("[!] 解密失败")
            return
        m = int32_be_at(p, MONEY_OFF)
        print(f"金币 @ {MONEY_OFF} = {m}  -> 游戏内 {m*10:,} G")
        for off in RES_OFFS:
            print(f"资源 @ {off} = {int16_be_at(p, off)}")
        return

    raise SystemExit("用法: --save 单个校验, 或 --save-a/--save-b 差分定位")


if __name__ == "__main__":
    main()
