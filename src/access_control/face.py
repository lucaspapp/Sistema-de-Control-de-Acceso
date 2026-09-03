import os
import cv2, time
import threading
import numpy as np
import requests
from pathlib import Path
from settings import load_local_env
from prohibited_store import FACES_DIR, person_for_recognition

PROJECT_ROOT=Path(__file__).resolve().parents[2]
load_local_env()
MODEL_DIR=PROJECT_ROOT/'assets'/'models'; PROHIBIDOS_DIR=PROJECT_ROOT/'assets'/'restricted_faces'; HISTORIAL_PROHIBIDOS=PROJECT_ROOT/'runtime'/'access_control'/'historial-prohibidos'
HISTORIAL_PROHIBIDOS.mkdir(parents=True,exist_ok=True)
FRIGATE_URL=os.getenv('FRIGATE_URL', 'http://127.0.0.1:5000')
YUNET_MODEL=MODEL_DIR/'face_detection_yunet_2023mar.onnx'
SFACE_MODEL=MODEL_DIR/'face_recognition_sface_2021dec.onnx'
RECOGNITION_THRESHOLD=0.40; REQUIRED_CONFIRMATIONS=1; MAX_SAMPLES_PER_TRACKING=60; SAMPLE_INTERVAL=0.7
MIN_FACE_WIDTH=45; MIN_FACE_HEIGHT=45; FACE_DETECTION_THRESHOLD=0.55

face_detector=None; face_recognizer=None; personas_prohibidas={}; http_session=requests.Session()

def cargar_modelos():
    global face_detector,face_recognizer
    for p in (YUNET_MODEL,SFACE_MODEL):
        if not p.exists(): raise FileNotFoundError(f'No existe modelo: {p}')
    face_detector=cv2.FaceDetectorYN.create(str(YUNET_MODEL),'',(320,320),FACE_DETECTION_THRESHOLD,0.3,5000)
    face_recognizer=cv2.FaceRecognizerSF.create(str(SFACE_MODEL),'')

def detectar_mejor_cara(imagen):
    if imagen is None or imagen.size==0:return None
    h,w=imagen.shape[:2]; face_detector.setInputSize((w,h)); _,faces=face_detector.detect(imagen)
    if faces is None:return None
    best=None; area_best=0
    for f in faces:
        x,y,fw,fh=map(float,f[:4]); conf=float(f[14])
        if conf<FACE_DETECTION_THRESHOLD or fw<MIN_FACE_WIDTH or fh<MIN_FACE_HEIGHT:continue
        area=fw*fh
        if area>area_best: area_best=area; best=f
    return best

def obtener_embedding(imagen):
    face=detectar_mejor_cara(imagen)
    if face is None:return None
    aligned=face_recognizer.alignCrop(imagen,face)
    if aligned is None or aligned.size==0:return None
    return face_recognizer.feature(aligned)

def cargar_prohibidos():
    # Producción usa únicamente perfiles administrados desde la web/SQLite.
    # assets/restricted_faces queda preservado como fuente heredada, sin uso.
    personas_prohibidas.clear()
    for person in person_for_recognition():
        path = FACES_DIR / person['image_path']
        img=cv2.imread(str(path)); emb=obtener_embedding(img) if img is not None else None
        if emb is not None:
            personas_prohibidas[person['name']]=emb; print(f"[FACE] Prohibido cargado desde la base: {person['name']}")
        else:
            print(f"[FACE] No se cargó {person['name']}: la foto no contiene una cara válida o clara.")

def reconocer(imagen):
    emb=obtener_embedding(imagen)
    if emb is None:return {'status':'NO_FACE','name':None,'score':0.0}
    if not personas_prohibidas:return {'status':'UNKNOWN','name':None,'score':0.0}
    name=None; best=-1.0
    for n,ref in personas_prohibidas.items():
        s=float(face_recognizer.match(emb,ref,cv2.FaceRecognizerSF_FR_COSINE))
        if s>best:best=s;name=n
    if best>=RECOGNITION_THRESHOLD:return {'status':'MATCH','name':name,'score':best}
    return {'status':'UNKNOWN','name':None,'score':max(0.0,best)}

def obtener_snapshot(event_id, camera=None):
    """Obtiene una captura del evento y usa la cámara como respaldo.

    Frigate puede demorar unos segundos en generar la snapshot de un evento
    recién creado; el respaldo evita descartar el tracking en ese intervalo.
    """
    url=f'{FRIGATE_URL}/api/events/{event_id}/snapshot-clean.webp'
    for _ in range(5):
        try:
            r=http_session.get(url,timeout=3)
            if r.status_code!=200:time.sleep(.15);continue
            img=cv2.imdecode(np.frombuffer(r.content,np.uint8),cv2.IMREAD_COLOR)
            if img is not None and img.size:return img
        except requests.RequestException:time.sleep(.15)
    if camera:
        try:
            r=http_session.get(f'{FRIGATE_URL}/api/{camera}/latest.jpg',timeout=3)
            if r.status_code==200:
                img=cv2.imdecode(np.frombuffer(r.content,np.uint8),cv2.IMREAD_COLOR)
                if img is not None and img.size:return img
        except requests.RequestException:
            pass
    return None

def recortar_persona(img,box):
    if img is None or not box or len(box)<4:return img
    try:x1,y1,x2,y2=[int(v) for v in box[:4]]
    except:return img
    h,w=img.shape[:2]; mx=int((x2-x1)*.15); my=int((y2-y1)*.15)
    x1=max(0,x1-mx);y1=max(0,y1-my);x2=min(w,x2+mx);y2=min(h,y2+my)
    return img[y1:y2,x1:x2] if x2>x1 and y2>y1 and img[y1:y2,x1:x2].size else img

def guardar_historial_prohibido(imagen,tracking_id,nombre,score):
    from datetime import datetime
    if imagen is None or imagen.size==0:return None
    d=HISTORIAL_PROHIBIDOS/datetime.now().strftime('%Y-%m-%d');d.mkdir(parents=True,exist_ok=True)
    p=d/f'{datetime.now().strftime("%H-%M-%S")}_{tracking_id}_{nombre}_{score:.3f}.jpg';cv2.imwrite(str(p),imagen)
    return str(p.relative_to(HISTORIAL_PROHIBIDOS.parent)).replace('\\', '/')

class FaceAnalyzer:
    def __init__(self):
        self._opencv_lock=threading.RLock()
        with self._opencv_lock:
            cargar_modelos();cargar_prohibidos()
        self.trackings={};self.last_reload=time.monotonic()
    def analizar_tracking(self,tracking_id,imagen):
        # FaceDetectorYN y FaceRecognizerSF no son seguros para uso concurrente.
        # Hay un hilo por persona, por lo que se serializa el acceso a OpenCV.
        with self._opencv_lock:
            return self._analizar_tracking(tracking_id,imagen)
    def _analizar_tracking(self,tracking_id,imagen):
        now=time.monotonic()
        # Permite que perfiles agregados desde la web estén disponibles sin
        # reiniciar el servicio de reconocimiento.
        if now-self.last_reload>=30:
            cargar_prohibidos();self.last_reload=now
        st=self.trackings.setdefault(tracking_id,{'samples':0,'confirmations':{},'scores':{},'last_sample':0.0,'alerted':False})
        if st['alerted']:return {'status':'MATCH','name':st['name'],'score':st['score'],'confirmed':True}
        if st['samples']>=MAX_SAMPLES_PER_TRACKING:return {'status':'UNKNOWN','name':None,'score':0.0,'confirmed':False}
        if now-st['last_sample']<SAMPLE_INTERVAL:return None
        st['last_sample']=now;res=reconocer(imagen);st['samples']+=1
        if res['status']!='MATCH':return {**res,'confirmed':False}
        n=res['name'];s=res['score'];st['confirmations'][n]=st['confirmations'].get(n,0)+1;st['scores'].setdefault(n,[]).append(s)
        avg=sum(st['scores'][n])/len(st['scores'][n]);confirmed=st['confirmations'][n]>=REQUIRED_CONFIRMATIONS and avg>=RECOGNITION_THRESHOLD
        if confirmed:st.update(alerted=True,name=n,score=avg);return {'status':'MATCH','name':n,'score':avg,'confirmed':True,'confirmations':st['confirmations'][n]}
        return {'status':'MATCH','name':n,'score':s,'confirmed':False,'confirmations':st['confirmations'][n]}
    def olvidar_tracking(self, tracking_id):
        """Libera las muestras cuando Frigate deja de seguir a la persona."""
        with self._opencv_lock:
            self.trackings.pop(tracking_id, None)
