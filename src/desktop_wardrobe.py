"""电脑版逐角色、逐姿态穿戴定位；只在内存合成，不改动原始美术。"""
from __future__ import annotations

from PIL import Image, ImageChops, ImageDraw, ImageFilter
import json
from functools import lru_cache


ROLES = ("xiaoyuan", "orange_adventurer", "xiaobao")
TUAN_POSES = ("idle", "smile", "wink", "wave", "celebrate", "proud", "sad", "cry", "surprise", "think", "tired", "sleep")
TUAN_ALIASES = {"walk": "wave", "attack": "wave", "happy": "smile", "hurt": "sad", "chest": "proud", "sit": "proud"}
# 原atlas不是等分排版；这些独立取样边界避免把邻格耳朵、尾巴带进当前动作。
TUAN_RECTS = {
    "idle": (0, 0, 375, 356), "smile": (375, 0, 731, 356),
    "wink": (731, 0, 1108, 357), "wave": (1108, 0, 1448, 357),
    "celebrate": (0, 355, 377, 704), "proud": (377, 352, 730, 704),
    "sad": (752, 361, 1119, 702), "cry": (1120, 361, 1448, 703),
    "surprise": (0, 704, 378, 1086), "think": (378, 704, 718, 1086),
    "tired": (718, 704, 1080, 1086), "sleep": (1070, 766, 1448, 1030),
}


def atlas_frame(atlas: Image.Image, pose: str) -> Image.Image:
    """独立裁出新版小团，保留主体及近旁表情颗粒，不带邻格碎片。"""
    name = TUAN_ALIASES.get(pose, pose)
    rect = TUAN_RECTS.get(name, TUAN_RECTS["idle"])
    scale_x, scale_y = atlas.width / 1448, atlas.height / 1086
    frame = atlas.crop(tuple(round(v * (scale_x if i % 2 == 0 else scale_y)) for i, v in enumerate(rect)))
    alpha = frame.getchannel("A")
    solid = alpha.point(lambda value: 255 if value >= 64 else 0)
    # 主体质心位于每个独立取样的中央；只用连通体确定主体范围，毛发边缘仍使用原alpha。
    center = (frame.width // 2, frame.height // 2)
    if solid.getpixel(center):
        ImageDraw.floodfill(solid, center, 128)
        body = solid.point(lambda value: 255 if value == 128 else 0)
        box = body.getbbox()
        if box:
            margin = 23 if name == "cry" else 3
            window = Image.new("L", frame.size)
            ImageDraw.Draw(window).rectangle((max(0, box[0] - margin), max(0, box[1] - margin),
                                             min(frame.width, box[2] + margin), min(frame.height, box[3] + margin)), fill=255)
            frame.putalpha(ImageChops.multiply(alpha, window))
    return frame


def normalize_frame(image: Image.Image) -> Image.Image:
    """所有角色共享落脚点；睡姿按宽度缩放，不拉成站姿。"""
    bounds = image.getchannel("A").point(lambda value: 255 if value >= 32 else 0).getbbox()
    if bounds:
        image = image.crop(bounds)
    factor = min(440 / max(1, image.width), 450 / max(1, image.height))
    image = image.resize((max(1, round(image.width * factor)), max(1, round(image.height * factor))), Image.Resampling.LANCZOS)
    frame = Image.new("RGBA", (512, 512))
    frame.alpha_composite(image, ((512 - image.width) // 2, 472 - image.height))
    return frame


def canonical_pose(role: str, pose: str) -> str:
    if role == "orange_adventurer":
        return TUAN_ALIASES.get(pose, pose) if pose in TUAN_POSES or pose in TUAN_ALIASES else "idle"
    aliases = {"smile": "happy", "wave": "walk", "proud": "chest",
               "sad": "hurt", "cry": "hurt", "sit": "think"}
    name=aliases.get(pose,pose)
    return name if name in ('idle','walk','think','attack','happy','hurt','celebrate','chest','wink','surprise','tired','sleep') else 'idle'


# 坐标为归一化后的512画布；body是衣身边界，hat是帽檐落点范围。
# front列出原角色应盖回衣服上方的头部/前爪/翅膀，避免动作时袖子压住手爪。
ANCHORS = {
    "xiaoyuan": {
        "idle": {"body": (103, 260, 413, 437), "hat": (208, 33, 413, 143), "face": 258, "front": [[(241,372),(293,372),(345,472),(276,480)], [(363,345),(421,350),(442,471),(374,478)]]},
        "walk": {"body": (95, 282, 410, 435), "hat": (216, 50, 420, 160), "face": 279, "front": [[(229,372),(304,364),(382,442),(357,474),(285,460)], [(347,353),(420,362),(449,432),(406,457)]]},
        "think": {"body": (139, 264, 432, 437), "hat": (183, 29, 397, 146), "face": 260, "front": [[(354,190),(408,199),(450,312),(419,357),(385,311)], [(265,360),(331,364),(349,479),(270,479)]]},
        "attack": {"body": (88, 303, 373, 426), "hat": (172, 65, 386, 183), "face": 303, "front": [[(352,269),(441,267),(446,328),(392,350)], [(223,380),(290,369),(331,447),(296,478),(253,453)]]},
        "happy": {"body": (103, 269, 397, 437), "hat": (172, 27, 386, 145), "face": 262, "front": [[(386,208),(443,213),(442,328),(404,366),(380,303)], [(258,359),(319,360),(335,479),(266,479)]]},
        "hurt": {"body": (145, 283, 422, 441), "hat": (180, 75, 399, 187), "face": 280, "front": [[(249,365),(310,365),(334,478),(254,478)], [(339,367),(405,367),(425,478),(347,478)]]},
        "celebrate": {"body": (152, 269, 405, 419), "hat": (190, 45, 405, 158), "face": 263, "front": [[(164,151),(231,156),(238,273),(192,312)], [(379,151),(443,152),(442,290),(397,327)]]},
        "chest": {"body": (128, 279, 395, 433), "hat": (175, 55, 385, 171), "face": 271, "front": [[(285,343),(511,308),(511,512),(264,512)], [(391,246),(456,245),(467,312),(395,318)]]},
    },
    "orange_adventurer": {
        "idle": {"body": (122, 286, 412, 434), "hat": (204, 21, 414, 134), "face": 280, "front": [[(237,370),(303,367),(320,479),(247,479)],[(325,366),(390,360),(414,479),(332,479)]]},
        "smile": {"body": (120, 285, 414, 433), "hat": (196, 25, 412, 138), "face": 283, "front": [[(240,367),(310,366),(371,447),(338,479),(268,450)],[(343,365),(405,360),(421,471),(349,475)]]},
        "wink": {"body": (119, 282, 410, 434), "hat": (201, 20, 416, 133), "face": 281, "front": [[(233,366),(307,366),(329,479),(253,479)],[(323,369),(389,362),(411,474),(333,476)]]},
        "wave": {"body": (122, 285, 404, 434), "hat": (170, 33, 390, 155), "face": 284, "front": [[(356,188),(449,174),(458,256),(408,361),(377,350)],[(237,369),(300,369),(325,479),(242,479)]]},
        "celebrate": {"body": (117, 298, 354, 423), "hat": (175, 34, 389, 153), "face": 288, "front": [[(108,87),(177,102),(205,277),(160,314)],[(349,172),(435,176),(426,262),(351,321)]]},
        "proud": {"body": (155, 284, 416, 432), "hat": (179, 20, 401, 145), "face": 280, "front": [[(244,350),(305,353),(324,479),(240,479)],[(328,354),(394,349),(418,479),(331,479)]]},
        "sad": {"body": (116, 290, 392, 433), "hat": (107, 42, 344, 174), "face": 288, "front": [[(153,342),(208,353),(221,474),(149,474)],[(233,353),(289,351),(302,476),(231,479)]]},
        "cry": {"body": (120, 300, 416, 434), "hat": (128, 39, 379, 176), "face": 299, "front": [[(211,379),(278,378),(297,479),(213,479)],[(295,378),(359,375),(386,479),(301,479)]]},
        "surprise": {"body": (112, 295, 413, 433), "hat": (198, 26, 414, 146), "face": 291, "front": [[(239,370),(306,366),(339,479),(261,479)],[(339,367),(398,359),(425,466),(352,472)]]},
        "think": {"body": (138, 286, 425, 434), "hat": (153, 27, 378, 150), "face": 284, "front": [[(288,236),(346,219),(397,284),(412,367),(363,387),(329,310)],[(220,365),(284,362),(310,479),(231,479)]]},
        "tired": {"body": (123, 274, 417, 429), "hat": (142, 28, 366, 148), "face": 273, "front": [[(232,348),(298,345),(359,469),(282,479)],[(315,346),(375,332),(426,459),(357,478)]]},
        "sleep": {"body": (62, 293, 301, 423), "hat": (282, 258, 431, 341), "face": 0, "angle": -9, "front": [[(265,301),(370,308),(466,387),(467,478),(232,479),(227,407)],[(29,405),(211,400),(274,476),(41,480)]]},
    },
    "xiaobao": {
        "idle": {"body": (113, 232, 390, 429), "hat": (139, 15, 350, 119), "face": 230, "front": [[(84,267),(188,235),(168,313),(103,362),(70,350)],[(350,241),(392,253),(432,334),(415,359),(377,341)]]},
        "walk": {"body": (117, 231, 380, 429), "hat": (144, 13, 351, 119), "face": 229, "front": [[(65,282),(190,237),(162,310),(75,342),(54,318)],[(364,239),(444,220),(461,257),(435,299),(374,308)]]},
        "think": {"body": (126, 237, 405, 433), "hat": (142, 14, 355, 119), "face": 232, "front": [[(363,181),(409,205),(432,278),(415,309),(377,280)],[(106,274),(191,242),(173,334),(113,363),(97,338)]]},
        "attack": {"body": (105, 244, 387, 428), "hat": (109, 17, 324, 123), "face": 236, "front": [[(366,230),(453,157),(472,172),(467,216),(395,279)],[(100,269),(187,247),(159,320),(82,342),(58,317)]]},
        "happy": {"body": (130, 263, 399, 427), "hat": (142, 39, 356, 149), "face": 251, "front": [[(57,199),(156,235),(191,278),(155,311),(81,281)],[(371,231),(435,190),(464,209),(449,254),(384,290)]]},
        "hurt": {"body": (119, 246, 400, 432), "hat": (134, 23, 346, 131), "face": 239, "front": [[(161,272),(237,262),(270,304),(232,356),(154,343)],[(326,266),(380,261),(412,311),(394,351),(342,330)]]},
        "celebrate": {"body": (142, 250, 399, 431), "hat": (142, 19, 355, 129), "face": 241, "front": [[(98,162),(140,177),(197,255),(179,304),(132,278),(99,220)],[(385,229),(414,133),(449,146),(453,189),(417,277)]]},
        "chest": {"body": (130, 254, 407, 440), "hat": (152, 18, 370, 127), "face": 242, "front": [[(137,257),(237,281),(463,223),(484,352),(351,409),(232,359),(159,326)]]},
    },
}


# 5.1新增真实眨眼/惊讶/疲惫/休眠图；复用相近站姿定位，睡姿独立定位及遮挡。
for role in ("xiaoyuan", "xiaobao"):
    ANCHORS[role]["wink"] = dict(ANCHORS[role]["idle"])
    ANCHORS[role]["surprise"] = dict(ANCHORS[role]["idle"])
    ANCHORS[role]["tired"] = dict(ANCHORS[role]["hurt"] if role == "xiaoyuan" else ANCHORS[role]["idle"])
ANCHORS["xiaoyuan"]["sleep"] = {"body": (64, 302, 302, 427), "hat": (296, 249, 432, 331), "face": 0,
    "front": [[(274,247),(466,247),(487,479),(269,479)], [(69,416),(281,407),(300,479),(45,479)]]}
ANCHORS["xiaobao"]["sleep"] = {"body": (270, 265, 401, 456), "hat": (72, 242, 207, 328), "face": 0, "angle": 90,
    "front": [[(0,233),(239,233),(270,395),(207,479),(0,479)], [(401,321),(511,312),(511,479),(394,479)]]}


def anchor(role: str, pose: str) -> dict:
    table = ANCHORS.get(role, ANCHORS["xiaoyuan"])
    return table.get(canonical_pose(role, pose), table["idle"])


# 足部独立定位；猫鞋覆盖后脚，前爪套覆盖前脚/举爪，企鹅为脚掌与翅套。
# 所有坐标使用既有512画布，待用户正式素材逐姿态视觉验收后冻结。


def limb_rects(role: str, pose: str, slot: str) -> list[tuple]:
    table=limb_config()[slot].get(role,limb_config()[slot]['xiaoyuan'])
    return table.get(canonical_pose(role,pose),table['idle'])


@lru_cache(maxsize=1)
def limb_config():
    from store import resource_path
    return json.loads(resource_path('assets/wardrobe_530.json').read_text(encoding='utf-8'))




def limb_layer(image: Image.Image, slot: str, role: str, pose: str) -> Image.Image:
    # 输入为正式成对原图派生，分离左右件再适配每个动作，不绘制占位装备。
    midpoint = image.width // 2
    parts = [image.crop((0,0,midpoint,image.height)), image.crop((midpoint,0,image.width,image.height))]
    canvas = Image.new('RGBA', (512,512))
    for index, rect in enumerate(limb_rects(role, pose, slot)):
        part = parts[index % 2]
        if part.getchannel('A').getbbox():
            angles=limb_config()['angles'].get(role,{}).get(slot,{}).get(canonical_pose(role,pose),[])
            canvas.alpha_composite(place(part, rect, rotate=angles[index] if index<len(angles) else 0))
    return canvas


def cropped(image: Image.Image) -> Image.Image:
    bounds = image.getchannel("A").point(lambda value: 255 if value >= 20 else 0).getbbox()
    return image.crop(bounds) if bounds else image


def place(image: Image.Image, rect: tuple, *, rotate: float = 0) -> Image.Image:
    """穿戴素材分别适配衣身/头顶，不把整个512旧画布固定叠加。"""
    x0, y0, x1, y1 = (round(value) for value in rect)
    layer = cropped(image).resize((max(1, x1-x0), max(1, y1-y0)), Image.Resampling.LANCZOS)
    if rotate:
        layer = layer.rotate(rotate, Image.Resampling.BICUBIC, expand=True)
        x0 -= (layer.width - (x1-x0)) // 2
        y0 -= (layer.height - (y1-y0)) // 2
    canvas = Image.new("RGBA", (512, 512))
    canvas.alpha_composite(layer, (x0, y0))
    return canvas


def garment_parts(image: Image.Image, item_id: str) -> tuple[Image.Image, Image.Image]:
    # 财管原图上部为帽、下部为衣身；星斗篷和工坊背带有相连装饰，按版式分区。
    cut = 0.39 if "xiaoyuan_ledger" in item_id else 0.41
    if item_id.endswith("stars"):
        cut = 0.39 if "xiaoyuan" in item_id else 0.42 if "orange_adventurer" in item_id else 0.45
    boundary = round(image.height * cut)
    return cropped(image.crop((0, boundary, image.width, image.height))), cropped(image.crop((0, 0, image.width, boundary)))


def garment_layer(base: Image.Image, cloth: Image.Image, role: str, pose: str) -> Image.Image:
    a = anchor(role, pose)
    result = place(cloth, a["body"], rotate=a.get("angle", 0))
    visible = base.getchannel("A").filter(ImageFilter.MaxFilter(13))
    front = Image.new("L", (512, 512))
    draw = ImageDraw.Draw(front)
    if a["face"]:
        draw.rectangle((0, 0, 511, a["face"]), fill=255)
    for polygon in a["front"]:
        draw.polygon(polygon, fill=255)
    front = front.filter(ImageFilter.GaussianBlur(1.1))
    result.putalpha(ImageChops.multiply(result.getchannel("A"), ImageChops.multiply(visible, ImageChops.invert(front))))
    return result


def accessory_layer(image: Image.Image, slot: str, role: str, pose: str, item_id: str = "") -> Image.Image:
    a = anchor(role, pose)
    bx0, by0, bx1, by1 = a["body"]
    if slot == "headwear":
        rect = a["hat"]
        # 简笔宽檐帽采用原图比例，避免普通帽子被拉成高帽。
        part = cropped(image)
        width = rect[2] - rect[0]
        height = min(rect[3] - rect[1], round(width * part.height / max(1, part.width)))
        return place(part, (rect[0], rect[3]-height, rect[2], rect[3]), rotate=-14 if canonical_pose(role, pose) == "sleep" else 0)
    if slot in ("xp", "coins"):
        center = (bx0 + bx1) / 2 + (-25 if slot == "xp" else 25)
        top = by0 + 18
        if canonical_pose(role, pose) == "sleep":
            center = bx0 + 104 + (-20 if slot == "xp" else 20)
            top = by0 + 45
        return place(image, (center-20, top, center+20, top+60), rotate=a.get("angle", 0))
    if item_id == "wonder_wings":
        rect = (max(5, bx0-103), max(45, by0-161), min(508, bx1+101), min(490, by1+20))
    elif item_id == "wonder_cape":
        rect = (max(15, bx0-45), by0-12, min(498, bx1+60), min(494, by1+57))
    elif item_id == "wonder_satchel":
        rect = (max(8, bx0-54), by0+4, bx0+82, min(476, by1+10))
    elif item_id == "wonder_broom":
        rect = (24, 423, 488, 507)
    elif item_id == "wonder_lantern":
        rect = (min(414, bx1+6), min(332, by0+34), min(504, bx1+92), min(488, by0+182))
    else:
        rect = (max(2, bx0-95), max(154, by0-59), max(98, bx0+5), 482)
    return place(image, rect)


def fitted_headwear(actor: Image.Image, image: Image.Image, role: str, pose: str, item_id: str, mouth=None):
    """保持帽子真实宽高比；给高帽预留头顶空间，最后整体缩放，不压扁帽冠。"""
    a = anchor(role, pose)
    x0, y0, x1, bottom = a["hat"]
    if item_id == "outfit_sky":
        # 飞行帽的耳罩落在脸颊两侧，开口让面部露出，不能把整顶罩帽顶在头顶。
        bottom += 52 if canonical_pose(role, pose) == "sleep" else 90 if role == "xiaobao" else 105
    part = cropped(image)
    factors = {"outfit_forest": 1.08, "outfit_island": 1.0, "outfit_snow": .9,
               "outfit_ruins": 1.07, "outfit_sky": 1.12, "outfit_stars": 1.02}
    width = round((x1-x0)*factors.get(item_id, 1))
    height = round(width*part.height/max(1, part.width))
    part = part.resize((width, max(1, height)), Image.Resampling.LANCZOS)
    angle = -16 if canonical_pose(role, pose) == "sleep" else -5 if canonical_pose(role, pose) in ("hurt", "sad", "cry", "think", "tired") else -3
    part = part.rotate(angle, Image.Resampling.BICUBIC, expand=True)
    left = round((x0+x1-part.width)/2)
    top = round(bottom-part.height)
    padding = max(0, 6-top)
    plane = Image.new("RGBA", (512, 512+padding))
    plane.alpha_composite(actor, (0, padding))
    # 接触阴影只落在角色轮廓内，帽檐有真实落点；不增加独立投影色块。
    shadow = Image.new("RGBA", plane.size)
    ImageDraw.Draw(shadow).ellipse((left+part.width*.1, bottom-10+padding, left+part.width*.9, bottom+10+padding), fill=(35, 26, 25, 48))
    shadow = shadow.filter(ImageFilter.GaussianBlur(4))
    shadow.putalpha(ImageChops.multiply(shadow.getchannel("A"), plane.getchannel("A")))
    plane.alpha_composite(shadow)
    plane.alpha_composite(part, (left, top+padding))
    if item_id == "outfit_sky":
        # 圆脸与鸟喙在耳罩的前方；保留面部轮廓，让护耳沿两侧包住头部。
        front = Image.new("L", plane.size)
        sleeping = canonical_pose(role, pose) == "sleep"
        center = (x0+x1)/2
        face_top = a["hat"][3] + (-12 if sleeping else 24)
        face_bottom = a["hat"][3] + 128 if sleeping else a["face"]+10
        radius = (x1-x0)*.44
        ImageDraw.Draw(front).ellipse((center-radius, face_top+padding, center+radius+10, face_bottom+padding), fill=255)
        front = front.filter(ImageFilter.GaussianBlur(2))
        original = Image.new("RGBA", plane.size)
        original.alpha_composite(actor, (0,padding))
        original.putalpha(ImageChops.multiply(original.getchannel("A"), front))
        plane.alpha_composite(original)
    result = normalize_frame(plane) if padding else plane
    if mouth is not None and padding:
        box = plane.getchannel("A").point(lambda value: 255 if value >= 32 else 0).getbbox()
        factor = min(440/(box[2]-box[0]), 450/(box[3]-box[1]))
        width, height = round((box[2]-box[0])*factor), round((box[3]-box[1])*factor)
        mouth = ((mouth[0]-box[0])*factor+(512-width)//2,
                 (mouth[1]+padding-box[1])*factor+472-height)
    return (result, mouth) if mouth is not None else result
