import time

ENTRADA_ZONAS=['zona_entrada','zona_pasando','zona_paso']; SALIDA_ZONAS=['zona_salida','zona_saliendo','zona_salio']; TRACKING_TIMEOUT=60

class Tracker:
    def __init__(self):self.personas={};self.entradas=0;self.salidas=0
    def crear(self,tid):
        if tid not in self.personas:self.personas[tid]={'entrada_step':0,'salida_step':0,'entrada_estado':'activo','salida_estado':'activo','entrada_contada':False,'salida_contada':False,'last_seen':time.time()}
        return self.personas[tid]
    def limpiar(self):
        now=time.time()
        for tid in [k for k,v in self.personas.items() if now-v['last_seen']>TRACKING_TIMEOUT]:del self.personas[tid]
    def secuencia(self,tid,zonas,tipo,actuales):
        p=self.personas[tid];step=p[f'{tipo}_step'];estado=p[f'{tipo}_estado'];contada=p[f'{tipo}_contada']
        if estado=='invalidada' or contada or step>=len(zonas):return False
        for z in zonas[step+1:]:
            if z in actuales:p[f'{tipo}_estado']='invalidada';return False
        if zonas[step] not in actuales:return False
        step+=1;p[f'{tipo}_step']=step
        if step==len(zonas):
            if tipo=='entrada':self.entradas+=1
            else:self.salidas+=1
            p[f'{tipo}_contada']=True;return True
        return False
    def procesar_evento(self,event):
        if event.get('type') not in ('new','update'):return None
        a=event.get('after') or {}
        if a.get('label')!='person':return None
        tid=a.get('id')
        if not tid:return None
        self.crear(tid)['last_seen']=time.time();actuales=set((a.get('current_zones') or [])+(a.get('entered_zones') or []))
        ent=self.secuencia(tid,ENTRADA_ZONAS,'entrada',actuales);sal=self.secuencia(tid,SALIDA_ZONAS,'salida',actuales);self.limpiar()
        if ent:return {'type':'entrada','tracking_id':tid,'camera':a.get('camera','unknown'),'event_id':tid,'box':a.get('box')}
        if sal:return {'type':'salida','tracking_id':tid,'camera':a.get('camera','unknown'),'event_id':tid,'box':a.get('box')}
        return None
