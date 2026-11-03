"""Pi 4 makeCourseの再現と、静止模型用に縮尺を変えた地形。"""
import math

VERSION = 'course-diorama-v1'
COURSE_PROFILES = ('rolling-v1','obstacles-v1','obstacles-55-7p5-v1')


def make_course(seed, profile):
    if type(seed) is not int or not 0 <= seed <= 2147483647 or profile not in COURSE_PROFILES:
        raise ValueError('invalid terrain course seed/profile')
    state=seed
    points=[[-8,0.0],[0,0.0],[6,0.0]]
    for x in range(9,173,3):
        state=(state+0x6d2b79f5)&0xffffffff
        t=((state^(state>>15))*(state|1))&0xffffffff
        t^=(t+((t^(t>>7))*(t|61)&0xffffffff))&0xffffffff
        rng=((t^(t>>14))&0xffffffff)/4294967296
        y=min(1,(x-6)/28)*(3.1*math.sin(x*.18)+1.4*math.sin(x*.53)+(rng-.5)*1.6)
        points.append([x,y])
    if profile=='obstacles-v1':
        heights={21:-.5,24:0,27:3,30:4.5,33:4.5,36:1.5,39:0,42:0,45:-3,48:-6,51:-6,54:-3,57:0,60:0}
        for p in points:
            if p[0] in heights:p[1]=heights[p[0]]
    if profile=='obstacles-55-7p5-v1':
        slope=math.tan(55*math.pi/180)
        heights={21:-.5,24:0,27:3*slope,30:4.5*slope,33:4.5*slope,36:1.5*slope,39:0,42:0,45:-3.75,48:-7.5,51:-7.5,54:-3.75,57:0,60:0}
        for p in points:
            if p[0] in heights:p[1]=heights[p[0]]
    return points


def terrain_for_source(source):
    seed=source['courseSeed'];profile=source.get('courseProfile','rolling-v1')
    course=make_course(seed,profile)
    # 9–66mを模型サイズへ圧縮。車体下だけ平らな展示台を兼ねる。
    points=[]
    for x,y in course:
        if 9<=x<=66:
            sx=(x-31.5)*.40
            if abs(sx)>2.4:points.append([sx,-1+(y-4.5)*.30])
    points.extend([[-2.4,-1.0],[2.4,-1.0]])
    points.sort()
    return {'version':VERSION,'courseSeed':seed,'courseProfile':profile,
            'sourceRange':[9,66],'scale':[.40,.30],'supportHalfWidth':2.4,'points':points}
