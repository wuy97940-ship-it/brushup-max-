"""答题所需曲线的原生矢量重绘；只读标记，不含书页图片。"""
from __future__ import annotations
import json
import math
import tkinter as tk
import customtkinter as ctk
import store

DIAGRAMS = json.loads(store.resource_path('assets/question_diagrams590.json').read_text(encoding='utf-8'))


def monotone_curve(points, steps=16):
    """逐点通过且分段不越过极值，标记点和最小风险/最低成本点保真。"""
    values=[]
    for axis in (0,1):
        series=[point[axis] for point in points]
        slopes=[b-a for a,b in zip(series,series[1:])]
        derivatives=[slopes[0]]
        derivatives.extend(2*a*b/(a+b) if a*b>0 else 0 for a,b in zip(slopes,slopes[1:]))
        derivatives.append(slopes[-1]);values.append((series,derivatives))
    result=[]
    for index in range(len(points)-1):
        for sample in range(steps):
            t=sample/steps
            result.append(tuple((2*t**3-3*t**2+1)*v[index]+(t**3-2*t**2+t)*d[index]
                 +(-2*t**3+3*t**2)*v[index+1]+(t**3-t**2)*d[index+1] for v,d in values))
    return [*result,points[-1]]


def capital_geometry():
    """无数字比例的示意：资本市场线切于M，X为风险资产曲线最左点。"""
    rf=(100,276);market=(402,153)
    slope=(market[1]-rf[1])/(market[0]-rf[0])
    minimum_y=270
    width=(minimum_y-market[1])/(-2*slope)
    minimum_x=market[0]-width
    def curve(t):return minimum_x+width*t*t,minimum_y-(minimum_y-market[1])*t
    def capital(x):return x,rf[1]+slope*(x-rf[0])
    sampled=[curve(start+(end-start)*i/32) for start,end in ((-.22,0),(0,1),(1,1.3)) for i in range(32)]
    return {'curve':[*sampled,curve(1.3)],'line':[rf,capital(650)],
            'Rf':rf,'M':curve(1),'N':curve(1.3),'X':curve(0),'P':capital(245),'Q':capital(548)}


class QuestionDiagram(ctk.CTkFrame):
    def __init__(self, master, diagram_id):
        super().__init__(master, height=300, corner_radius=12, fg_color='#F6F9FD')
        self.diagram_id = diagram_id
        self.pack_propagate(False)
        self.canvas = tk.Canvas(self, bg='#F6F9FD', highlightthickness=0)
        self.canvas.pack(fill='both', expand=True, padx=8, pady=8)
        self.canvas.bind('<Configure>', lambda event: self.draw())

    def draw(self):
        c = self.canvas
        w,h = c.winfo_width(),c.winfo_height()
        if w<20 or h<20:return
        c.delete('all')
        scale=min(w/820,h/410)
        ox=(w-820*scale)/2;oy=(h-410*scale)/2
        def xy(x,y):return ox+x*scale,oy+y*scale
        def line(points, **kw):
            coords=[v for x,y in points for v in xy(x,y)]
            return c.create_line(*coords, fill=kw.pop('fill','#3977AD'), width=max(1,2*scale), **kw)
        def text(x,y,value,anchor='center'):
            return c.create_text(*xy(x,y),text=value,fill='#234564',font=('Microsoft YaHei UI',max(9,round(15*scale))),anchor=anchor)
        def point(x,y,name,dx=0,dy=-18):
            px,py=xy(x,y);radius=max(2,3*scale)
            c.create_oval(px-radius,py-radius,px+radius,py+radius,fill='#3977AD',outline='')
            text(x+dx,y+dy,name)
        kind=DIAGRAMS[self.diagram_id]['kind']
        line([(100,355),(755,355)],fill='#536B80',arrow='last')
        line([(100,355),(100,38)],fill='#536B80',arrow='last')
        text(110,18,'成本金额' if kind=='working_capital' else '期望报酬率（%）',anchor='w')
        text(790,387,'流动资产金额' if kind=='working_capital' else '标准差（%）',anchor='e')
        if kind=='opportunity':
            m,n,q=(585,75),(435,300),(100,225)
            line([m,n],dash=(5,4));line([m,q,n])
            def curve(t, amplitude):return 585-150*t-amplitude*math.sin(math.pi*t),75+225*t
            for amplitude in (235,90):line([curve(i/64,amplitude) for i in range(65)])
            for x,y,name,dx in ((*m,'M',18),(*n,'N',15),(*q,'Q',-18),(*curve(.65,235),'P',-16),(*curve(.65,90),'O',18)):
                point(x,y,name,dx=dx,dy=0)
        elif kind in ('capital_market','capital_market_pq'):
            geometry=capital_geometry()
            line(geometry['curve']);line(geometry['line'])
            point(*geometry['Rf'],'Rf',dx=-23,dy=0);point(*geometry['M'],'M')
            if kind=='capital_market_pq':
                point(*geometry['P'],'P',dy=-18);point(*geometry['Q'],'Q')
            else:
                point(*geometry['N'],'N',dx=8,dy=19);point(*geometry['X'],'X',dx=15,dy=0)
        elif kind=='efficient_frontier':
            line(monotone_curve([(430,317),(245,308),(197,280),(275,225),(430,155),(620,68)]))
            line([(430,317),(620,68)],dash=(5,4))
            for x,y,name,dx,dy in ((430,317,'X',0,18),(197,280,'R',-18,0),(275,225,'T',-10,-15),(430,155,'W',-10,-15),(620,68,'Y',12,-12)):
                point(x,y,name,dx,dy)
        elif kind=='working_capital':
            line([(105,355),(650,110)])
            line(monotone_curve([(135,88),(188,212),(355,268),(635,284)]))
            line(monotone_curve([(155,58),(238,136),(355,173),(420,165),(560,83)]))
            line([(355,173),(355,355)],dash=(4,4))
            point(355,355,'M',dy=21);point(475,355,'N',dy=21)
            text(335,113,'相关总成本');text(660,157,'流动资产持有成本');text(654,290,'流动资产短缺成本');text(100,375,'0')
