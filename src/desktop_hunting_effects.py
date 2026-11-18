"""有界Canvas投题图形；只画已选精灵的招式，不读取或修改作答/奖励。"""
from __future__ import annotations
import math

KINDS = frozenset(('question', 'leaf', 'dandelion', 'pinecone', 'bubble', 'windbell',
                   'dew', 'feather', 'starwave', 'aurora', 'starlight', 'cloud', 'sand',
                   'lightning', 'rice', 'flame', 'holy_light', 'petal'))

def draw_ultimate(canvas, skill, width, height, scale, progress, *, reduced_motion=False):
    """专属弹道、震波和命中闪光；图元有界，减少动画时只保留静态招式提示。"""
    tags=('hunt_ultimate','ultimate_'+skill['projectile'])
    color=skill['color'];power=skill['power']
    x=width*(.77-.54*min(1,progress/.65));y=height*.55
    if not reduced_motion:
        draw_projectile(canvas,skill['projectile'],x,y,scale*(1+.4*power),progress,rarity=skill.get('tier','mythic'))
        if progress>.45:
            radius=(20+power*16)*scale*(.5+progress)
            for index in range(power+1):
                r=radius+index*9*scale
                canvas.create_oval(width*.23-r,y-r*.7,width*.23+r,y+r*.7,outline=color,width=max(1,(4-index)*scale),tags=tags)
            for index in range(6+power*4):
                angle=index*math.tau/(6+power*4)
                distance=radius*(.65+(index%3)*.22)
                canvas.create_line(width*.23+math.cos(angle)*distance,y+math.sin(angle)*distance*.7,
                    width*.23+math.cos(angle)*(distance+12*scale),y+math.sin(angle)*(distance+12*scale)*.7,
                    fill=color,width=2*scale,tags=tags)
            if .48<progress<.7:
                canvas.create_line(width*.10,height*.82,width*.36,height*.26,fill='#FFF6D8',width=(4+power*2)*scale,tags=tags)
    title=canvas.create_text(width*.5,height*.14,text='大招 · '+skill['skill'],fill=color,
        font=('Microsoft YaHei UI',round((14+power)*scale),'bold'),tags=tags)
    box=canvas.bbox(title)
    plate=canvas.create_rectangle(box[0]-12,box[1]-4,box[2]+12,box[3]+4,fill='#253B59',outline=color,width=scale,tags=tags)
    canvas.tag_lower(plate,title)


def draw_projectile(canvas, kind, x, y, scale, progress, *, rarity='common'):
    """每帧至多几十个小图元，全部带同一演出tag，缩放不改轨迹时间。"""
    kind = kind if kind in KINDS else 'question'
    tags = ('hunt_projectile', 'projectile_' + kind)
    s = scale

    def oval(cx, cy, rx, ry, fill, outline='', width=1):
        return canvas.create_oval(x + (cx-rx)*s, y + (cy-ry)*s,
                                  x + (cx+rx)*s, y + (cy+ry)*s,
                                  fill=fill, outline=outline, width=width*s, tags=tags)

    def line(points, color, width=2, **kwargs):
        coords = [value for px, py in points for value in (x+px*s, y+py*s)]
        return canvas.create_line(*coords, fill=color, width=width*s, tags=tags, **kwargs)

    def polygon(points, fill, outline='', width=1):
        coords = [value for px, py in points for value in (x+px*s, y+py*s)]
        return canvas.create_polygon(*coords, fill=fill, outline=outline, width=width*s, tags=tags)

    def star(cx, cy, radius=5, color='#FFE79A'):
        points = []
        for i in range(10):
            angle = i*math.pi/5-math.pi/2
            r = radius if i % 2 == 0 else radius*.42
            points.append((cx+math.cos(angle)*r, cy+math.sin(angle)*r))
        polygon(points, color, '#F5C969')

    def grain(cx, cy, angle=0, color='#FFFEF7'):
        # 斜长的真实米粒轮廓，避免白色问号球。
        ca, sa = math.cos(angle), math.sin(angle)
        points = [(cx+dx*ca-dy*sa, cy+dx*sa+dy*ca)
                  for dx, dy in ((-4, 0), (-2.7, -1.6), (2.7, -1.6), (4, 0), (2.7, 1.6), (-2.7, 1.6))]
        polygon(points, color, '#B8C4CE', .7)

    if kind == 'holy_light':
        oval(0,0,24,13,'#FFE190','#FFF9D8',2)
        oval(0,0,17,8,'#FFF7DA','#EAC269',1)
        star(-5,0,15,'#FFFFFF')
        for i in range(6):
            angle=i*math.tau/6
            oval(math.cos(angle)*31,math.sin(angle)*21,3,5,'#DCC288','#FFF1BB',.7)
        for i in range(3):
            line(((29+i*7,-8+i*7),(63+i*6,-8+i*7)), '#C6F5FF', 1.5)
    elif kind == 'petal':
        for i in range(9):
            px=-20+i*10;py=math.sin(progress*4+i*.7)*12
            polygon(((px-6,py),(px-3,py-5),(px+3,py-6),(px+6,py-1),(px+2,py+4)),
                    '#F5AEC9' if i%2 else '#E9C2F4','#FFF0F6',.6)
        line(((-28,7),(-7,0),(24,8),(63,-6)), '#D8B3E7', 1, smooth=True)
    elif kind == 'flame':
        polygon(((-25,7),(-12,-9),(-6,-24),(5,-12),(15,-21),(27,-3),(18,13),(0,19)), '#F48235', '#FFE5A3', 1)
        polygon(((-12,7),(-4,-7),(4,-13),(13,1),(8,12),(0,15)), '#FFD777')
        for i in range(4):
            oval(30+i*11,math.sin(progress*6+i)*5,5-i*.7,3-i*.3,'#F8B05A')
    elif kind == 'lightning':
        bolt = [(-28, 8), (-12, -4), (-5, 5), (7, -8), (14, -1), (29, -12)]
        line(bolt, '#F2B845', 9, joinstyle='round')
        line(bolt, '#FFE96B', 5, joinstyle='round')
        line(bolt, '#FFFCE8', 1.8)
        line(((5, -2), (10, 12), (21, 7)), '#FFE96B', 2)
        line(((-8, 0), (-15, -14), (-24, -10)), '#FFED8B', 2)
        for i in range(3):
            dx = 34+i*15
            line(((dx, -5), (dx+7, 2), (dx+13, -4)), '#FFE28B', 1.5)
        star(-29, 8, 5)
    elif kind == 'rice':
        # 有颗粒的蓬松白米饭，米粒拖尾与饭团本体同色。
        oval(0, 0, 21, 13, '#FAF8EF', '#AABAC8', 1.2)
        for i, (cx, cy) in enumerate(((-15, -4), (-8, -9), (0, -10), (9, -8), (16, -3),
                                     (-17, 3), (-8, 0), (1, -2), (10, 0), (16, 4),
                                     (-9, 7), (0, 6), (9, 7), (-2, 1))):
            grain(cx, cy, (i % 5-2)*.35)
        for i in range(5):
            grain(29+i*10, math.sin(progress*math.pi*2+i)*5, -.6+i*.28)
    elif kind == 'leaf':
        polygon(((-18, 1), (-8, -13), (7, -12), (19, -4), (11, 10), (-3, 13)), '#87DDB3', '#397D62')
        line(((-17, 1), (15, -5)), '#E4FFE8', 1.6)
        for i in (-1, 1):
            oval(25, i*8, 4, 2, '#F7CADB')
    elif kind == 'dandelion':
        for i in range(10):
            angle = i*math.tau/10
            px, py = math.cos(angle)*14, math.sin(angle)*14
            line(((0, 0), (px, py)), '#D5E9D9', 1)
            oval(px, py, 4, 3, '#FFFFEE', '#B5CABC', .7)
        oval(0, 0, 4, 4, '#EFDB87')
        line(((5, 12), (15, 24)), '#92B798', 1.4)
    elif kind == 'pinecone':
        oval(0, 0, 13, 19, '#BD814B', '#794B32', 1.2)
        for cy in (-10, -2, 6, 14):
            line(((-9, cy), (0, cy+4), (9, cy)), '#EDC38B', 1.6)
        polygon(((10, -14), (20, -23), (26, -13)), '#8BBE69', '#5D8D52')
    elif kind in ('bubble', 'dew'):
        if kind == 'bubble':
            oval(0, 0, 18, 18, '#A5E3F6', '#F4FCFF', 1.8)
            oval(-6, -7, 5, 3, '#F4FCFF')
        else:
            polygon(((0, -23), (-14, 1), (-11, 12), (0, 17), (11, 12), (14, 1)), '#8EDCF2', '#E9FBFF', 1.4)
            oval(-5, 4, 3, 6, '#DFF9FF')
        for i in range(3):
            oval(26+i*12, i*4-4, 4-i*.7, 4-i*.7, '#BAF0FD', '#EDF9FF', .7)
    elif kind == 'windbell':
        polygon(((-13, -14), (9, -14), (15, 9), (-18, 9)), '#F7D77B', '#BB934F', 1.4)
        line(((-18, 9), (15, 9)), '#FFF1B1', 2)
        line(((-2, 8), (-2, 24)), '#BD9751', 1.4)
        oval(-2, 22, 4, 3, '#FEE7A4')
        line(((24, -11), (37, -16), (47, -7)), '#D9F4DC', 2, smooth=True)
    elif kind == 'feather':
        polygon(((-20, 12), (-13, -6), (3, -17), (18, -14), (19, -1), (7, 9)), '#A8DFFF', '#E9F5FF', 1.4)
        line(((-22, 16), (15, -13)), '#FBE49E', 2)
        for i in range(3):
            star(28+i*13, -6+i*6, 3.5)
    elif kind == 'starwave':
        for cy, color in ((-5, '#86C4FF'), (3, '#D3EAFF')):
            points = [(px, cy+math.sin(px/12+progress*3)*6) for px in range(-24, 61, 7)]
            line(points, color, 4, smooth=True)
        star(0, -7, 11)
        star(25, 8, 5)
        star(49, -9, 3)
    elif kind == 'aurora':
        for cy, color in ((-9, '#91E9DA'), (0, '#B6C0FF'), (9, '#EDC4F2')):
            points = [(px, cy+math.sin(px/18+progress*2)*8) for px in range(-26, 58, 7)]
            line(points, color, 4, smooth=True)
        star(-10, 0, 6, '#F1E9FF')
    elif kind == 'starlight':
        star(0, 0, 19)
        star(27, -7, 5, '#FFF4C9')
        star(43, 8, 3.5, '#FFF4C9')
    elif kind == 'cloud':
        oval(-10, 3, 13, 10, '#DDF4FF', '#A8CADF')
        oval(1, -4, 16, 13, '#EAF8FF', '#A8CADF')
        oval(15, 3, 13, 10, '#DDF4FF', '#A8CADF')
        line(((-16, 6), (2, 10), (22, 6)), '#AFD9E9', 2, smooth=True)
        for i in range(3):
            oval(34+i*10, -5+i*5, 3, 2, '#C4EAFE')
    elif kind == 'sand':
        oval(0, 0, 21, 21, '', '#EECF87', 1.6)
        for i in range(8):
            a = i*math.tau/8
            line(((math.cos(a)*17, math.sin(a)*17), (math.cos(a)*21, math.sin(a)*21)), '#FFF1BD', 1)
        for i in range(10):
            angle = i*2.4+progress
            oval(math.cos(angle)*12, math.sin(angle)*12, 1.7, 1.7, '#F9DF97')
        line(((0, -11), (0, 0), (9, 4)), '#FFF4C9', 1.7)
    else:
        oval(0, 0, 16, 12, '#88D9FF', '#ECFAFF', 2)
        canvas.create_text(x, y, text='?', fill='#27558C',
                           font=('Microsoft YaHei UI', round(17*s), 'bold'), tags=tags)

    if rarity in ('legendary', 'mythic') and progress >= .86:
        for i in range(5):
            angle = i*math.tau/5
            star(math.cos(angle)*30, math.sin(angle)*25, 3, '#F4E9BA')
    if rarity == 'mythic':
        oval(0, 0, 29, 23, '', '#F3D89D', 1)
    return kind
