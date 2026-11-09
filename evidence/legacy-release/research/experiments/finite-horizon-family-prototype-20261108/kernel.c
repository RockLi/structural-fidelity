#include <stdint.h>
#include <math.h>
#include <float.h>
#include <string.h>
// Each R encloses the exact rational expression. One outward binary64 ULP
// per primitive operation covers its rounding. No unsafe reassociation/FMA.
// Exact adjacent binary64 value, equivalent to nextafter(x, +/-infinity).
// Bit steps avoid repeated external libm calls; validated separately.
double audit_adjacent(double x,int upward){
 if(isnan(x)||(upward?x==INFINITY:x==-INFINITY))return x;
 if(x==0)return upward?DBL_TRUE_MIN:-DBL_TRUE_MIN;
 uint64_t bits;memcpy(&bits,&x,8);
 if((x>0)==(upward!=0))bits++;else bits--;
 memcpy(&x,&bits,8);return x;
}
static double outward(double x,double direction){return audit_adjacent(x,direction>0);}
typedef struct {double l,h;} R;
static R P(double x){return (R){x,x};}
static R add(R a,R b){return (R){outward(a.l+b.l,-INFINITY),outward(a.h+b.h,INFINITY)};}
static R sub(R a,R b){return (R){outward(a.l-b.h,-INFINITY),outward(a.h-b.l,INFINITY)};}
static R mul(R a,R b){double z[4]={a.l*b.l,a.l*b.h,a.h*b.l,a.h*b.h};double l=z[0],h=z[0];for(int i=1;i<4;i++){l=fmin(l,z[i]);h=fmax(h,z[i]);}return (R){outward(l,-INFINITY),outward(h,INFINITY)};}
static R divr(R a,R b){R inv={outward(1/b.h,-INFINITY),outward(1/b.l,INFINITY)};return mul(a,inv);}
static R absr(R a){return (R){a.l<=0 && a.h>=0 ? 0:fmin(fabs(a.l),fabs(a.h)), fmax(fabs(a.l),fabs(a.h))};}
static R maxr(R a,R b){return (R){fmax(a.l,b.l),fmax(a.h,b.h)};}
static R neg(R a){return (R){-a.h,-a.l};}
typedef struct {R l,h;} I;
static I interval(float l,float h){return (I){P(l),P(h)};}
static R maxabs(I x){return maxr(absr(x.l),absr(x.h));}
static I ipadd(I x,I y){return (I){add(x.l,y.l),add(x.h,y.h)};}
static I ipsub(I x,I y){return (I){sub(x.l,y.h),sub(x.h,y.l)};}
static I scale(I x,R a){return (I){mul(x.l,a),mul(x.h,a)};} // a >= 0
static I pad(I x,R e){return (I){sub(x.l,e),add(x.h,e)};}
static float floor32(double x){float f=(float)x;if((double)f>x)f=nextafterf(f,-INFINITY);return f;}
static float ceil32(double x){float f=(float)x;if((double)f<x)f=nextafterf(f,INFINITY);return f;}
static int grid(I x,float *out,int positive){
 if(positive){x.l.l=fmax(0,x.l.l);x.l.h=fmax(0,x.l.h);x.h.l=fmax(0,x.h.l);x.h.h=fmax(0,x.h.h);}
 float a=floor32(x.l.l),b=floor32(x.l.h),c=ceil32(x.h.l),d=ceil32(x.h.h);
 if(!isfinite(a)||!isfinite(d)||a!=b||c!=d)return 0;
 out[0]=a==0?0:a;out[1]=d==0?0:d;return 1;
}
typedef int (*Fallback)(int,const float*,const float*,int,float,float*);
typedef struct {int certified,slot,target,reason,steps,thresholds,events,fallbacks,trace_rows;double slack;} Result;
static void accumulate(const float*x,const float*values,int n,float field,float*out,Fallback fb,Result*r){
 R u=P(0x1p-24),tiny=P(0x1p-149),sum=P(0);for(int j=0;j<n;j++)sum=add(sum,P(values[j]));
 float inject=field*0.01f;sum=add(sum,P(inject));R m=P(n+1),mu=mul(m,u),den=sub(P(1),mu);
 R gamma=divr(mu,den);I old=interval(x[0],x[1]);R rho=add(mul(gamma,add(maxabs(old),sum)),divr(mul(m,tiny),den));
 I z=pad((I){add(old.l,sum),add(old.h,sum)},rho);
 if(!grid(z,out,1)){r->fallbacks++;if(!fb(0,x,values,n,field,out))r->reason=99;}
}
static void voltage(const float*x,float*out,Fallback fb,Result*r){
 R u=P(0x1p-24),tiny=P(0x1p-149),h=P((double)0.1f);
 I v=interval(x[0],x[1]),ge=interval(x[2],x[3]),gi=interval(x[4],x[5]);
 I syn=ipsub(ge,gi);R e1=add(mul(u,maxabs(syn)),tiny);
 I z=ipadd((I){neg(v.h),neg(v.l)},pad(syn,e1));R e2=add(mul(u,maxabs(z)),tiny);
 I prod=scale(pad(z,e2),h);R e3=add(mul(u,maxabs(prod)),tiny);
 I end=ipadd(v,pad(prod,e3));R e4=add(mul(u,maxabs(end)),tiny);
 I center=ipadd(scale(v,sub(P(1),h)),scale(syn,h));
 R rho=add(add(mul(h,add(e1,e2)),e3),e4);
 if(!grid(pad(center,rho),out,0)){r->fallbacks++;if(!fb(1,x,0,0,0,out))r->reason=99;}
}
static void decay(const float*x,float*out,Fallback fb,Result*r){
 R u=P(0x1p-24),tiny=P(0x1p-149),d=P((double)(1.0f-0.1f));I old=interval(x[0],x[1]);
 R rho=add(mul(mul(u,d),maxabs(old)),tiny);
 if(!grid(pad(scale(old,d),rho),out,0)){r->fallbacks++;if(!fb(2,x,0,0,0,out))r->reason=99;}
}
// flag columns: reference execution, reference spike, due, pending, ref status.
// fields: original field before / after update. T=300; rows target-major.
int run(int mode,int nt,int T,const int32_t*flags,const float*fields,const int32_t*offsets,const float*events,Result*r,float*trace,Fallback fb){
 memset(r,0,sizeof(*r));r->certified=1;r->slot=r->target=-1;r->slack=INFINITY;
 for(int k=0;k<nt;k++){
  float v[2]={-65,-65},ge[2]={0,0},gi[2]={0,0};int active=0,deadline=0;
  for(int n=0;n<T;n++){
   int row=k*T+n;const int32_t*f=flags+row*5;const float*fld=fields+row*2;
   r->steps++;int exec=active||f[2];int reason=0;
   if(exec!=f[0]){reason=1;goto fail;}
   int eligible=deadline<=n;
   if(exec){
    int b=offsets[row*2],mid=offsets[row*2+1],end=offsets[row*2+2];r->events+=end-b;
    if(mode==0){float e[2],i[2];accumulate(ge,events+b,mid-b,fld[0],e,fb,r);accumulate(gi,events+mid,end-mid,0,i,fb,r);memcpy(ge,e,8);memcpy(gi,i,8);}
    else {for(int j=b;j<mid;j++)ge[0]+=events[j];for(int j=mid;j<end;j++)gi[0]+=events[j];float inject=fld[0]*0.01f;ge[0]+=inject;gi[0]+=0.0f;ge[1]=ge[0];gi[1]=gi[0];}
    if(r->reason==99){reason=99;goto fail;}
    if(eligible){
     float vp[2];r->thresholds++;
     if(mode==0){float x[6]={v[0],v[1],ge[0],ge[1],gi[0],gi[1]};voltage(x,vp,fb,r);}
     else {float syn=ge[0]-gi[0];float z=-v[0]+syn;float dv=z*0.1f;vp[0]=v[0]+dv;vp[1]=vp[0];}
     if(r->reason==99){reason=99;goto fail;}
     double slack=f[1] ? (double)vp[0]-30.0 : 30.0-(double)vp[1];
     if((f[1]&&slack<0)||(!f[1]&&slack<=0)){reason=2;goto fail;}
     r->slack=fmin(r->slack,slack);
     if(f[1]){v[0]=v[1]=-65;deadline=n+2;}else memcpy(v,vp,8);
     if(mode==0){float e[2],i[2];decay(ge,e,fb,r);decay(gi,i,fb,r);memcpy(ge,e,8);memcpy(gi,i,8);}
     else {ge[0]*=(1.0f-0.1f);gi[0]*=(1.0f-0.1f);ge[1]=ge[0];gi[1]=gi[0];}
    }else if(f[1]){reason=98;goto fail;}
    if(r->reason==99){reason=99;goto fail;}
    int fixed=f[1]||f[2]||fabsf(fld[1])>1e-6f;
    int lo=fixed||ge[0]>1e-6f||gi[0]>1e-6f,hi=fixed||ge[1]>1e-6f||gi[1]>1e-6f;
    if(lo!=hi){reason=3;goto fail;}
    int status=lo?1:f[3]?2:0;
    if(status!=f[4]){reason=4;goto fail;}
    active=lo||f[3];
   }else {if(f[1]){reason=5;goto fail;}active=0;}
   if(trace){float*dst=trace+(r->trace_rows)*6;memcpy(dst,v,8);memcpy(dst+2,ge,8);memcpy(dst+4,gi,8);}r->trace_rows++;continue;
   fail:r->certified=0;r->slot=n;r->target=k;r->reason=reason;return 0;
  }
 }
 return 1;
}

// Arithmetic-only validation entry point; no graph or network generation.
int audit_operation(int op,const float*x,const float*values,int n,float field,float*out,Fallback fb,int force_fallback){
 Result r={0};
 if(force_fallback)return fb(op,x,values,n,field,out)?1:-1;
 if(op==0)accumulate(x,values,n,field,out,fb,&r);
 else if(op==1)voltage(x,out,fb,&r);
 else if(op==2)decay(x,out,fb,&r);
 else return -1;
 return r.reason==99?-1:r.fallbacks;
}
// Amortize the Python/ctypes boundary equally; keep identical single-call kernels.
int run_batch(int repetitions,int mode,int nt,int T,const int32_t*flags,const float*fields,const int32_t*offsets,const float*events,Result*r,Fallback fb){
 int answer=0;
 for(int i=0;i<repetitions;i++)answer=run(mode,nt,T,flags,fields,offsets,events,r,0,fb);
 return answer;
}

// Family model: parameter symbols remain common across all edges and slots.
// Every R bounds its exact-real coefficient; err is an upper error-radius bound.
typedef struct {R c,p[2],err;} Aff;
typedef struct {Aff input;R upper;int m;} Agg;
static Aff ac(double c){Aff z={0};z.c=P(c);return z;}
static Aff aa(Aff x,Aff y){Aff z;z.c=add(x.c,y.c);for(int j=0;j<2;j++)z.p[j]=add(x.p[j],y.p[j]);z.err=add(x.err,y.err);return z;}
static Aff an(Aff x){x.c=neg(x.c);for(int j=0;j<2;j++)x.p[j]=neg(x.p[j]);return x;}
static Aff as(Aff x,R c){x.c=mul(x.c,c);for(int j=0;j<2;j++)x.p[j]=mul(x.p[j],c);x.err=mul(x.err,c);return x;} // c>=0
static R magnitude(R x){return P(fmax(fabs(x.l),fabs(x.h)));}
static R expand(R x,R err){return (R){outward(x.l-err.h,-INFINITY),outward(x.h+err.h,INFINITY)};}
static R ar(Aff x,int d,int method){
 R z;
 if(method==0){R rad=P(0);for(int j=0;j<d;j++)rad=add(rad,absr(x.p[j]));z=(R){sub(x.c,rad).l,add(x.c,rad).h};}
 else {z=(R){INFINITY,-INFINITY};for(int mask=0;mask<(1<<d);mask++){R v=x.c;for(int j=0;j<d;j++)v=(mask&(1<<j))?add(v,x.p[j]):sub(v,x.p[j]);z.l=fmin(z.l,v.l);z.h=fmax(z.h,v.h);}}
 return expand(z,x.err);
}
int family_model(int d,double rho,int rows,const float*fields,const int32_t*offsets,const float*base,const float*weights,const int32_t*signs,Agg*out){
 if(d<1||d>2||rho<0||rho>.25)return 0;
 R u=P(0x1p-24),tiny=P(0x1p-149);
 for(int row=0;row<rows;row++)for(int ch=0;ch<2;ch++){
  int ix=row*2+ch,b=offsets[ix],end=offsets[ix+1];Agg z={0};
  for(int k=b;k<end;k++){
   Aff v=ac(base[k]);R upper=P(base[k]);
   if(weights[k]>0){
    v=ac((double)weights[k]*100.0); // exact: binary32 * integer100 fits binary64
    for(int j=0;j<d;j++)v.p[j]=mul(P(v.c.l),P(rho*signs[k*2+j]/d));
    R wm=mul(P(weights[k]),add(P(1),P(rho)));
    R we=add(mul(u,wm),tiny);
    R amp=mul(P(100),add(wm,we));
    v.err=add(mul(P(100),we),add(mul(u,amp),tiny));
    upper=add(mul(P(100),wm),v.err);
   }
   z.input=aa(z.input,v);z.upper=add(z.upper,upper);
  }
  float inject=ch==0?fields[row*2]*0.01f:0.0f;
  z.input=aa(z.input,ac(inject));z.upper=add(z.upper,P(inject));z.m=end-b+1;
  out[ix]=z;
 }
 return 1;
}
static Aff aacc(Aff x,Agg in,int d,int method){
 R u=P(0x1p-24),tiny=P(0x1p-149),m=P(in.m),den=sub(P(1),mul(m,u));
 R gamma=divr(mul(m,u),den);
 R rho=add(mul(gamma,add(magnitude(ar(x,d,method)),in.upper)),divr(mul(m,tiny),den));
 x=aa(x,in.input);x.err=add(x.err,rho);return x;
}
static Aff avoltage(Aff v,Aff ge,Aff gi,int d,int method){
 R u=P(0x1p-24),tiny=P(0x1p-149),h=P((double)0.1f);
 R vr=ar(v,d,method),syn=sub(ar(ge,d,method),ar(gi,d,method));
 R e1=add(mul(u,magnitude(syn)),tiny);
 R z=sub(expand(syn,e1),vr),e2=add(mul(u,magnitude(z)),tiny);
 R prod=mul(expand(z,e2),h),e3=add(mul(u,magnitude(prod)),tiny);
 R end=add(vr,expand(prod,e3)),e4=add(mul(u,magnitude(end)),tiny);
 Aff out=aa(as(v,sub(P(1),h)),as(aa(ge,an(gi)),h));
 out.err=add(out.err,add(add(mul(h,add(e1,e2)),e3),e4));return out;
}
static Aff adecay(Aff g,int d,int method){
 R decay=P((double)(1.0f-0.1f)),u=P(0x1p-24),tiny=P(0x1p-149);
 R rho=add(mul(mul(u,decay),magnitude(ar(g,d,method))),tiny);
 g=as(g,decay);g.err=add(g.err,rho);return g;
}
int family_run(int method,int d,int nt,int T,const int32_t*flags,const float*fields,const Agg*inputs,Result*r,double*trace){
 memset(r,0,sizeof(*r));r->certified=1;r->slot=r->target=-1;r->slack=INFINITY;
 for(int k=0;k<nt;k++){
  Aff v=ac(-65),ge=ac(0),gi=ac(0);int active=0,deadline=0;
  for(int n=0;n<T;n++){
   int row=k*T+n;const int32_t*f=flags+row*5;int execute=active||f[2],reason=0;r->steps++;
   if(execute!=f[0]){reason=1;goto fail;}
   if(execute){
    r->events+=inputs[row*2].m+inputs[row*2+1].m-2;
    ge=aacc(ge,inputs[row*2],d,method);gi=aacc(gi,inputs[row*2+1],d,method);
    if(deadline<=n){
     Aff vp=avoltage(v,ge,gi,d,method);R bound=ar(vp,d,method);r->thresholds++;
     double slack=f[1]?bound.l-30:30-bound.h;
     if((f[1]&&slack<0)||(!f[1]&&slack<=0)){reason=2;goto fail;}
     r->slack=fmin(r->slack,slack);v=f[1]?ac(-65):vp;if(f[1])deadline=n+2;
     ge=adecay(ge,d,method);gi=adecay(gi,d,method);
    }else if(f[1]){reason=98;goto fail;}
    R er=ar(ge,d,method),ir=ar(gi,d,method);
    int fixed=f[1]||f[2]||fabsf(fields[row*2+1])>1e-6f;
    int lo=fixed||er.l>(double)1e-6f||ir.l>(double)1e-6f;
    int hi=fixed||er.h>(double)1e-6f||ir.h>(double)1e-6f;
    if(lo!=hi){reason=3;goto fail;}
    int status=lo?1:f[3]?2:0;
    if(status!=f[4]){reason=4;goto fail;}active=lo||f[3];
   }else{if(f[1]){reason=5;goto fail;}active=0;}
   if(trace){R b[3]={ar(v,d,method),ar(ge,d,method),ar(gi,d,method)};for(int j=0;j<3;j++){trace[r->trace_rows*6+j*2]=b[j].l;trace[r->trace_rows*6+j*2+1]=b[j].h;}}
   r->trace_rows++;continue;
   fail:r->certified=0;r->slot=n;r->target=k;r->reason=reason;return 0;
  }
 }
 return 1;
}
int family_batch(int repetitions,int method,int d,int nt,int T,const int32_t*flags,const float*fields,const Agg*inputs,Result*r){
 int answer=0;for(int i=0;i<repetitions;i++)answer=family_run(method,d,nt,T,flags,fields,inputs,r,0);return answer;
}
void point_events(int d,double rho,const double*alpha,int J,const float*base,const float*weights,const int32_t*signs,float*out){
 for(int k=0;k<J;k++){
  if(weights[k]<=0){out[k]=base[k];continue;}
  double z=0;for(int j=0;j<d;j++)z+=alpha[j]*signs[k*2+j];
  float w=(float)((double)weights[k]*(1+rho*z/d));out[k]=w*100.0f;
 }
}
int points_batch(int reps,int d,double rho,int count,const double*alphas,int J,const float*base,const float*weights,const int32_t*signs,int nt,int T,const int32_t*flags,const float*fields,const int32_t*offsets,float*scratch,Result*results,Fallback fb){
 int passes=0;for(int rep=0;rep<reps;rep++)for(int i=0;i<count;i++){
  point_events(d,rho,alphas+i*d,J,base,weights,signs,scratch);
  int ok=run(1,nt,T,flags,fields,offsets,scratch,results+i,0,fb);if(rep==0)passes+=ok;
 }
 return passes;
}
int cached_points_batch(int reps,int count,int J,const float*streams,int nt,int T,const int32_t*flags,const float*fields,const int32_t*offsets,Result*results,Fallback fb){
 int passes=0;for(int rep=0;rep<reps;rep++)for(int i=0;i<count;i++){
  int ok=run(1,nt,T,flags,fields,offsets,streams+i*J,results+i,0,fb);if(rep==0)passes+=ok;
 }
 return passes;
}
int agg_size(void){return sizeof(Agg);}
