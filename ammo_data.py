from typing import Dict, Union

# Dictionary storing ammo data in format: {ammo_name: (category, damage, penetration)}
# For buckshot, damage is stored as "8x37" to represent 8 pellets of 37 damage each
AMMO_DATA: Dict[str, tuple[str, Union[str, int], int]] = {
    # 12 Gauge Shot
    "5.25MM BUCKSHOT": ("12 Gauge Shot", "8x37", 1),
    "8.5MM MAGNUM BUCKSHOT": ("12 Gauge Shot", "8x50", 2),
    "6.5MM EXPRESS BUCKSHOT": ("12 Gauge Shot", "9x35", 3),
    "7MM BUCKSHOT": ("12 Gauge Shot", "8x39", 3),
    "PIRANHA": ("12 Gauge Shot", "10x25", 24),
    "FLECHETTE": ("12 Gauge Shot", "8x25", 31),
    
    # 12 Gauge Slugs
    "RIP": ("12 Gauge Slugs", 265, 2),
    "SUPERFORMANCE HP SLUG": ("12 Gauge Slugs", 220, 5),
    "GRIZZLY 40 SLUG": ("12 Gauge Slugs", 190, 12),
    "COPPER SABOT HP SLUG": ("12 Gauge Slugs", 206, 14),
    "LEAD SLUG": ("12 Gauge Slugs", 167, 15),
    "DUAL SABOT SLUG": ("12 Gauge Slugs", "2x85", 17),
    "POLEVA-3 SLUG": ("12 Gauge Slugs", 140, 17),
    "FTX CUSTOM LITE SLUG": ("12 Gauge Slugs", 183, 20),
    "POLEVA-6U SLUG": ("12 Gauge Slugs", 150, 20),
    "MAKESHIFT .50 BMG SLUG": ("12 Gauge Slugs", 197, 26),
    "AP-20 ARMOR-PIERCING SLUG": ("12 Gauge Slugs", 164, 37),
    
    # 20 Gauge
    "5.6MM BUCKSHOT": ("20 Gauge", "8x26", 1),
    "6.2MM BUCKSHOT": ("20 Gauge", "8x22", 2),
    "7.5MM BUCKSHOT": ("20 Gauge", "8x25", 3),
    "7.3MM BUCKSHOT": ("20 Gauge", "9x23", 3),
    "DEVASTATOR SLUG": ("20 Gauge", 198, 5),
    "POLEVA-3 SLUG (20GA)": ("20 Gauge", 120, 14),
    "STAR SLUG": ("20 Gauge", 154, 16),
    "POLEVA-6U SLUG (20GA)": ("20 Gauge", 135, 17),
    "TSS ARMOR PIERCING SLUG": ("20 Gauge", 155, 30),
    "DANGEROUS GAME SLUG": ("20 Gauge", 143, 25),
    "FLECHETTE (20GA)": ("20 Gauge", 20, 24),
    
    # 23x75 mm
    "ZVEZDA FLASHBANG ROUND": ("23x75 mm", 0, 0),
    "SHRAPNEL-25 BUCKSHOT": ("23x75 mm", "8x78", 10),
    "SHRAPNEL-10 BUCKSHOT": ("23x75 mm", "8x87", 11),
    "BARRIKADA SLUG": ("23x75 mm", 192, 39),
    
    # 9x18 mm
    "PM SP8 GZH": ("9x18 mm", 67, 1),
    "PM SP7 GZH": ("9x18 mm", 77, 2),
    "PM PSV": ("9x18 mm", 69, 3),
    "PM P GZH": ("9x18 mm", 50, 5),
    "PM PSO GZH": ("9x18 mm", 54, 5),
    "PM PS GS PPO": ("9x18 mm", 55, 6),
    "PM PRS GS": ("9x18 mm", 58, 6),
    "PM PPE GZH": ("9x18 mm", 61, 7),
    "PM PPT GZH": ("9x18 mm", 59, 8),
    "PM PST GZH": ("9x18 mm", 50, 12),
    "PM RG028 GZH": ("9x18 mm", 65, 13),
    "PM BZHT GZH": ("9x18 mm", 53, 18),
    "PMM PSTM GZH": ("9x18 mm", 58, 24),
    "PM PBM GZH": ("9x18 mm", 40, 28),
    
    # 7.62x25 mm
    "TT LRNPC": ("7.62x25 mm", 66, 7),
    "TT LRN": ("7.62x25 mm", 64, 8),
    "TT FMJ43": ("7.62x25 mm", 60, 11),
    "TT AKBS": ("7.62x25 mm", 58, 12),
    "TT P GL": ("7.62x25 mm", 58, 14),
    "TT PT GZH": ("7.62x25 mm", 55, 18),
    "TT PST GZH": ("7.62x25 mm", 50, 25),
    
    # 9x19 mm
    "RIP (9X19)": ("9x19 mm", 102, 2),
    "QUAKEMAKER": ("9x19 mm", 85, 8),
    "PSO GZH (9X19)": ("9x19 mm", 59, 10),
    "LUGER CCI": ("9x19 mm", 70, 10),
    "T GZH (9X19)": ("9x19 mm", 58, 14),
    "M882": ("9x19 mm", 56, 18),
    "PST GZH (9X19)": ("9x19 mm", 54, 20),
    "AP 6.3": ("9x19 mm", 52, 30),
    "PBP GZH": ("9x19 mm", 44, 39),
    
    # .45 ACP
    "ACP RIP": (".45 ACP", 130, 3),
    "ACP HYDRA-SHOK": (".45 ACP", 100, 13),
    "ACP LASERMATCH FMJ": (".45 ACP", 76, 19),
    "ACP MATCH FMJ": (".45 ACP", 72, 25),
    "ACP AP": (".45 ACP", 66, 38),
    
    # .50
    "AE JHP": (".50", 147, 12),
    "HAWK JSP": (".50", 122, 26),
    "AE COPPER SOLID": (".50", 94, 33),
    "AE FMJ": (".50", 85, 40),
    
    # 9x21 mm
    "PE GZH": ("9x21 mm", 80, 15),
    "P GZH (9X21)": ("9x21 mm", 65, 18),
    "PS GZH (9X21)": ("9x21 mm", 59, 22),
    "7U4": ("9x21 mm", 53, 27),
    "BT GZH (9X21)": ("9x21 mm", 52, 32),
    "7N42": ("9x21 mm", 49, 38),
    
    # .357 Magnum
    "SOFT POINT": (".357 Magnum", 108, 12),
    "HP (.357)": (".357 Magnum", 99, 18),
    "JHP": (".357 Magnum", 88, 24),
    "FMJ (.357)": (".357 Magnum", 70, 35),
    
    # 5.7x28 mm
    "R37.F": ("5.7x28 mm", 98, 8),
    "SS198LF": ("5.7x28 mm", 70, 17),
    "R37.X": ("5.7x28 mm", 81, 11),
    "SS197SR": ("5.7x28 mm", 62, 25),
    "L191": ("5.7x28 mm", 53, 33),
    "SB193": ("5.7x28 mm", 59, 27),
    "SS190": ("5.7x28 mm", 49, 37),
    
    # 4.6x30 mm
    "ACTION SX": ("4.6x30 mm", 65, 18),
    "SUBSONIC SX": ("4.6x30 mm", 52, 23),
    "JSP SX": ("4.6x30 mm", 46, 32),
    "FMJ SX": ("4.6x30 mm", 43, 40),
    "AP SX": ("4.6x30 mm", 35, 53),
    
    # 9x39 mm
    "FMJ (9X39)": ("9x39 mm", 75, 17),
    "SP-5 GS": ("9x39 mm", 71, 28),
    "SPP GS": ("9x39 mm", 68, 35),
    "PAB-9 GS": ("9x39 mm", 62, 43),
    "SP-6 GS": ("9x39 mm", 60, 48),
    "BP GS": ("9x39 mm", 58, 54),
    
    # .366 TKM
    "TKM GEKSA": (".366 TKM", 110, 14),
    "TKM FMJ": (".366 TKM", 98, 23),
    "TKM EKO": (".366 TKM", 73, 30),
    "TKM AP-M": (".366 TKM", 90, 42),
    
    # 5.45x39 mm
    "HP (5.45)": ("5.45x39 mm", 76, 9),
    "PRS GS": ("5.45x39 mm", 70, 13),
    "SP (5.45)": ("5.45x39 mm", 67, 15),
    "US GS": ("5.45x39 mm", 65, 17),
    "T GS": ("5.45x39 mm", 59, 20),
    "FMJ (5.45)": ("5.45x39 mm", 55, 24),
    "PS GS": ("5.45x39 mm", 56, 28),
    "PP GS": ("5.45x39 mm", 51, 34),
    "BT GS": ("5.45x39 mm", 54, 37),
    "7N40": ("5.45x39 mm", 55, 42),
    "BP GS": ("5.45x39 mm", 48, 45),
    "BS GS": ("5.45x39 mm", 45, 54),
    "PPBS GS IGOLNIK": ("5.45x39 mm", 37, 62),
    
    # 5.56x45 mm
    "WARMAGEDDON": ("5.56x45 mm", 88, 3),
    "HP (5.56)": ("5.56x45 mm", 79, 7),
    "MK 255 MOD 0": ("5.56x45 mm", 72, 11),
    "M856": ("5.56x45 mm", 60, 18),
    "FMJ (5.56)": ("5.56x45 mm", 57, 23),
    "M855": ("5.56x45 mm", 54, 31),
    "MK 318 MOD 0": ("5.56x45 mm", 53, 33),
    "M856A1": ("5.56x45 mm", 52, 38),
    "M855A1": ("5.56x45 mm", 49, 44),
    "M995": ("5.56x45 mm", 42, 53),
    "SSA AP": ("5.56x45 mm", 38, 57),
    
    # 7.62x39 mm
    "HP (7.62X39)": ("7.62x39 mm", 80, 15),
    "SP (7.62X39)": ("7.62x39 mm", 68, 20),
    "FMJ (7.62X39)": ("7.62x39 mm", 63, 26),
    "US GZH": ("7.62x39 mm", 56, 29),
    "T-45M1 GZH": ("7.62x39 mm", 65, 30),
    "PS GZH (7.62X39)": ("7.62x39 mm", 61, 35),
    "PP (7.62X39)": ("7.62x39 mm", 59, 41),
    "BP GZH": ("7.62x39 mm", 58, 47),
    "MAI AP": ("7.62x39 mm", 53, 58),
    
    # .300 Blackout
    "BLACKOUT WHISPER": (".300 Blackout", 90, 14),
    "BLACKOUT V-MAX": (".300 Blackout", 72, 20),
    "BLACKOUT BCP FMJ": (".300 Blackout", 60, 30),
    "BLACKOUT M62 TRACER": (".300 Blackout", 54, 36),
    "BLACKOUT CBJ": (".300 Blackout", 58, 43),
    "BLACKOUT AP": (".300 Blackout", 51, 48),
    
    # 6.8x51 mm
    "SIG FMJ": ("6.8x51 mm", 80, 36),
    "SIG HYBRID": ("6.8x51 mm", 72, 47),
    
    # 7.62x51 mm
    "ULTRA NOSLER": ("7.62x51 mm", 105, 15),
    "TCW SP": ("7.62x51 mm", 85, 30),
    "BCP FMJ (7.62X51)": ("7.62x51 mm", 83, 37),
    "M62 TRACER": ("7.62x51 mm", 82, 42),
    "M80": ("7.62x51 mm", 80, 43),
    "M61": ("7.62x51 mm", 70, 64),
    "M993": ("7.62x51 mm", 67, 70),
    "M80A1": ("7.62x51 mm", 73, 60),
    
    # 7.62x54R
    "HP BT": ("7.62x54R", 102, 23),
    "SP BT": ("7.62x54R", 92, 27),
    "FMJ (7.62X54R)": ("7.62x54R", 84, 33),
    "T-46M GZH": ("7.62x54R", 82, 41),
    "LPS GZH": ("7.62x54R", 81, 42),
    "PS GZH (7.62X54R)": ("7.62x54R", 84, 45),
    "BT GZH": ("7.62x54R", 78, 55),
    "SNB GZH": ("7.62x54R", 75, 62),
    "BS GS": ("7.62x54R", 72, 70),
    
    # 12.7x55 mm
    "PS12A": ("12.7x55 mm", 165, 10),
    "PS12": ("12.7x55 mm", 115, 28),
    "PS12B": ("12.7x55 mm", 102, 46),
    
    # .338 Lapua Magnum
    "TAC-X": (".338 Lapua Magnum", 196, 18),
    "UCW": (".338 Lapua Magnum", 142, 32),
    "FMJ (.338)": (".338 Lapua Magnum", 122, 47),
    "AP (.338)": (".338 Lapua Magnum", 115, 79),
    
    # Mounted Weapons
    "30MM GRENADE": ("Mounted Weapons", 199, 1),
    "12.7X108MM": ("Mounted Weapons", 182, 88),
    "12.7X108MM TRACER": ("Mounted Weapons", 199, 80),
    
    # Other
    "40MM BUCKSHOT GRENADE": ("Other", 160, 5)
}
