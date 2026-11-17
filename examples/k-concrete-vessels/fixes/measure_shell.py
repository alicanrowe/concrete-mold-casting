import trimesh,glob,numpy as np,sys,os
from shapely.geometry import LineString
A=float(sys.argv[1]); a=np.radians(A);n=np.array([np.cos(a),np.sin(a),0]);t=np.array([-np.sin(a),np.cos(a),0])
c=np.array([0.0,-85.0])
ms={f.split('/')[-1]:trimesh.load(f) for f in sorted(glob.glob(sys.argv[2]+'/[ABC]*.stl'))+sorted(glob.glob(sys.argv[2]+'/D*.stl'))}
ms={k:m for k,m in ms.items() if (m.vertices@n).max()>150}
TH=np.radians(np.arange(0,360,1.0)); D=np.arange(150,208,2.0)
sin_=np.full((len(D),len(TH)),np.nan)
for i,d in enumerate(D):
    segs=[]
    for k,m in ms.items():
        s=m.section(plane_origin=n*d,plane_normal=n)
        if s is None: continue
        for e in s.discrete: segs.append(LineString(np.c_[e@t,e[:,2]]-c))
    for j,th in enumerate(TH):
        ray=LineString([(0,0),(700*np.cos(th),700*np.sin(th))]); hs=[]
        for ls in segs:
            x=ray.intersection(ls)
            for p in ([x] if x.geom_type=='Point' else list(getattr(x,'geoms',[]))):
                if p.geom_type=='Point': hs.append(np.hypot(p.x,p.y))
        if hs: sin_[i,j]=min(hs)
np.savez(os.path.join(os.path.dirname(os.path.abspath(__file__)),f'shell{int(A)}.npz'),sin=sin_,D=D,TH=TH)
