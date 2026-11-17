import trimesh,glob,numpy as np,sys,json,os
A=float(sys.argv[1]); a=np.radians(A);n=np.array([np.cos(a),np.sin(a),0]);t=np.array([-np.sin(a),np.cos(a),0])
c=np.array([0.0,-85.0])
cores=[f for f in sorted(glob.glob(sys.argv[2]+'/K*.stl'))]
ms={f.split('/')[-1]:trimesh.load(f) for f in cores}
ms={k:m for k,m in ms.items() if (m.vertices@n).max()>150}
print(list(ms))
TH=np.radians(np.arange(0,360,1.0)); D=np.arange(150,200,2.0)
out=np.full((len(D),len(TH)),np.nan); inn=np.full_like(out,np.nan); own=np.empty((len(D),len(TH)),object)
from shapely.geometry import LineString
for i,d in enumerate(D):
    segs=[]
    for k,m in ms.items():
        s=m.section(plane_origin=n*d,plane_normal=n)
        if s is None: continue
        for e in s.discrete:
            p=np.c_[e@t,e[:,2]]-c; segs.append((k,LineString(p)))
    for j,th in enumerate(TH):
        ray=LineString([(0,0),(600*np.cos(th),600*np.sin(th))])
        hits=[]
        for k,ls in segs:
            x=ray.intersection(ls)
            if x.is_empty: continue
            pts=[x] if x.geom_type=='Point' else list(getattr(x,'geoms',[]))
            for p in pts:
                if p.geom_type=='Point': hits.append((np.hypot(p.x,p.y),k))
        if hits:
            hits.sort(); out[i,j]=hits[-1][0]; inn[i,j]=hits[0][0]; own[i,j]=hits[-1][1]
np.savez(os.path.join(os.path.dirname(os.path.abspath(__file__)),f'rho{int(A)}.npz'),out=out,inn=inn,D=D,TH=TH,own=own.astype(str))
for i,d in enumerate(D): print(d, np.isnan(out[i]).sum(), np.nanmean(out[i]).round(1), np.nanmean(out[i]-inn[i]).round(1))
