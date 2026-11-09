#include <math.h>
#include <stdint.h>
#include <stdlib.h>
#include <float.h>
// Ordered binary64, no FMA. Each stream row is (target chunk,time), sources ascending.
static const double dt=0.0001, ce=-0.0001/0.005, ci=-0.0001/0.010, base=-0.065+0.018, reset=-0.060;
static double up(double x){return nextafter(x,INFINITY);}
static double plus(double x,double y){return up(x+y);}
static double times(double x,double y){return up(x*y);}
static double ab(double x){return fabs(x);}
typedef struct{double m,a,e;} Aff;
static double mag(Aff x,double rho){return plus(plus(ab(x.m),times(ab(x.a),rho)),x.e);}
static double gcoef=0x1p-48; // 32u, exceeds gamma_8 for binary64.
static double tiny=0x1p-1068; // 64 minimum subnormals.
// Radius recurrence uses consolidated linear coefficients; rounding does not cancel.
static Aff decay(Aff x,double c,double rho){
 double b=1+c,db=up(DBL_EPSILON*(1+ab(c))); // encloses |RN(1+c)-(1+c)|
 Aff y;y.m=c*x.m+x.m;y.a=b*x.a;
 double ds=plus(times(db,ab(x.a)),times(gcoef,times(ab(b),ab(x.a))));
 double re=plus(times(gcoef,times(1+ab(c),mag(x,rho))),tiny);
 y.e=plus(plus(times(plus(ab(b),db),x.e),times(rho,ds)),times(2,re));return y;
}
static Aff addweight(Aff x,double w,double sign,double rho){
 Aff y;double wa=sign*w;y.m=x.m+w;y.a=x.a+wa;
 double we=plus(times(gcoef,times(ab(w),1+rho)),tiny);
 double ds=plus(times(gcoef,plus(ab(x.a),ab(wa))),tiny);
 double re=plus(times(gcoef,plus(mag(x,rho),times(ab(w),1+rho))),tiny);
 y.e=plus(plus(plus(x.e,we),times(rho,ds)),times(2,re));return y;
}
static Aff voltage(Aff v,Aff ge,Aff gi,double drive,double tau,double rho){
 double h=dt/tau,b=1-h,dh=up(DBL_EPSILON*ab(h)),db=up(DBL_EPSILON*(1+ab(h)));
 Aff y;y.m=(dt*((base+(drive+ge.m))-(gi.m+v.m)))/tau+v.m;
 y.a=b*v.a+h*(ge.a-gi.a);
 double ds=plus(times(db,ab(v.a)),times(dh,plus(ab(ge.a),ab(gi.a))));
 ds=plus(ds,times(gcoef,plus(times(ab(b),ab(v.a)),times(ab(h),plus(ab(ge.a),ab(gi.a))))));
 double mv=mag(v,rho),me=mag(ge,rho),mi=mag(gi,rho),hu=plus(ab(h),dh);
 double norm=plus(mv,times(hu,plus(plus(ab(base),ab(drive)),plus(plus(me,mi),mv))));
 double re=plus(times(gcoef,norm),times(tiny,1+1/tau));
 y.e=plus(plus(times(plus(ab(b),db),v.e),times(hu,plus(ge.e,gi.e))),plus(times(rho,ds),times(2,re)));return y;
}
// Arrays: offsets[2*T+1], channel[event], weight[event], sign[event], refsp[T*8], drive[T*2].
int point(int T,int limit,const int64_t*off,const uint8_t*ch,const double*w,const double*sg,double alpha,const double*tau,const double*theta,const double*drive,const uint8_t*refsp,double*out,double*pre,uint8_t*eligible){
 double ge[2]={0},gi[2]={0},v[8];int last[8];for(int k=0;k<8;k++){v[k]=reset;last[k]=-100000000;}
 for(int n=0;n<limit;n++){
  int mismatch=-1;
  for(int q=0;q<2;q++){
   for(int j=0;j<4;j++){
    int k=4*q+j,ok=n-last[k]>=20;double z=v[k];if(ok)z=(dt*((base+(drive[2*n+q]+ge[q]))-(gi[q]+z)))/tau[k]+z;
    if(pre)pre[n*8+k]=z;if(eligible)eligible[n*8+k]=ok;
    int fire=ok && z>=theta[k];if(fire){z=reset;last[k]=n;}v[k]=z;
    if(fire!=refsp[n*8+k] && mismatch<0)mismatch=k;
   }
   ge[q]=ce*ge[q]+ge[q];gi[q]=ci*gi[q]+gi[q];
   int row=q*T+n;for(int64_t z=off[row];z<off[row+1];z++){double ww=w[z]*(1+sg[z]*alpha);if(ch[z])gi[q]+=ww;else ge[q]+=ww;}
   if(out)for(int j=0;j<4;j++){int k=q*4+j;out[(n*8+k)*3]=v[k];out[(n*8+k)*3+1]=ge[q];out[(n*8+k)*3+2]=gi[q];}
  }
  if(mismatch>=0)return n*8+mismatch;
 }
 return -1;
}
int certify(int T,int limit,const int64_t*off,const uint8_t*ch,const double*w,const double*sg,double rho,const double*tau,const double*theta,const double*drive,const uint8_t*refsp,double*out){
 Aff ge[2]={{0}},gi[2]={{0}},v[8];int last[8];for(int k=0;k<8;k++){v[k]=(Aff){reset,0,0};last[k]=-100000000;}
 for(int n=0;n<limit;n++){
  for(int q=0;q<2;q++){
   for(int j=0;j<4;j++){
    int k=4*q+j,ok=n-last[k]>=20;
    if(ok){v[k]=voltage(v[k],ge[q],gi[q],drive[n*2+q],tau[k],rho);double rad=plus(times(ab(v[k].a),rho),v[k].e),lo=nextafter(v[k].m-rad,-INFINITY),hi=up(v[k].m+rad);
     if(!isfinite(rad)||!isfinite(lo)||!isfinite(hi))return n*8+k;
     if(refsp[n*8+k] ? lo<theta[k] : hi>=theta[k])return n*8+k;
    }else if(refsp[n*8+k])return n*8+k;
    if(refsp[n*8+k]){v[k]=(Aff){reset,0,0};last[k]=n;}
   }
   ge[q]=decay(ge[q],ce,rho);gi[q]=decay(gi[q],ci,rho);int row=q*T+n;
   for(int64_t z=off[row];z<off[row+1];z++){if(ch[z])gi[q]=addweight(gi[q],w[z],sg[z],rho);else ge[q]=addweight(ge[q],w[z],sg[z],rho);}
   if(out)for(int j=0;j<4;j++){int k=q*4+j;Aff states[3]={v[k],ge[q],gi[q]};for(int d=0;d<3;d++){Aff x=states[d];int ix=((n*8+k)*3+d)*3;out[ix]=x.m;out[ix+1]=x.a;out[ix+2]=x.e;}}
  }
 }
 return -1;
}
