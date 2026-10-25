// Classic worker: MediaPipe's WASM loader uses importScripts internally.
let face, detailFace, FaceLandmarker, hands, pose, HandLandmarker, PoseLandmarker, fileset, surface, context, handsEnabled = true, poseEnabled = true;
let handGeneration = 0,poseFrame=0,cachedPose=null,cachedHands=null,cachedHandsAt=0,preferGPU=false;
async function createDetector(Task,options){
    if(preferGPU&&trackingBackend!=='nvidia_gpu'){
        try{return await Task.createFromOptions(fileset,{...options,baseOptions:{...options.baseOptions,delegate:'GPU'}});}
        catch(_){/* Some Android WebViews lack worker WebGL. Use CPU there. */}
    }
    return Task.createFromOptions(fileset,options);
}
let trackingBackend = 'mediapipe', leapSocket = null, leapFrame = null, leapFrameAt = 0, leapConnected = false, mapLeapFrame;
importScripts('/static/js/tracking-distance.js?v=far2');
let detailSurface, detailContext, faceRegion=null, faceRegionTime=0, frameCount=0, faceConfirmations=0;
function detailImage(image,roi){
    detailContext.drawImage(image,roi.x*image.width,roi.y*image.height,roi.width*image.width,roi.height*image.height,0,0,512,512);
    return detailSurface;
}

async function configureBodyTracking(enabled) {
    handsEnabled = Boolean(enabled);
    cachedPose=null;poseFrame=0;
    cachedHands=null;cachedHandsAt=0;
    const generation = ++handGeneration;
    if (!handsEnabled) {
        hands?.close(); hands = null;
    }
    if (!fileset) return;
    if (handsEnabled && trackingBackend !== 'leap_motion' && !hands) {
        const detector = await createDetector(HandLandmarker, {
            baseOptions: {modelAssetPath: '/static/vendor/tracking/hand_landmarker.task', delegate: trackingBackend === 'nvidia_gpu' ? 'GPU' : 'CPU'},
            runningMode: 'VIDEO', numHands: 2,
            minHandDetectionConfidence: .7, minHandPresenceConfidence: .7,
            minTrackingConfidence: .65,
        });
        if (generation !== handGeneration || !handsEnabled) { detector.close(); return; }
        hands = detector;
    }
    if (poseEnabled && !pose) {
        const detector = await createDetector(PoseLandmarker, {
            baseOptions: {modelAssetPath: '/static/vendor/tracking/pose_landmarker_lite.task', delegate: trackingBackend === 'nvidia_gpu' ? 'GPU' : 'CPU'},
            runningMode: 'VIDEO', numPoses: 1,
            minPoseDetectionConfidence: 0.45, minPosePresenceConfidence: 0.45,
            minTrackingConfidence: 0.45, outputSegmentationMasks: false,
        });
        if (generation !== handGeneration || !poseEnabled) { detector.close(); return; }
        pose = detector;
    }
}

self.onmessage = async ({data}) => {
    try {
        if (data.type === 'hands-enabled') {
            await configureBodyTracking(data.enabled);
            return;
        }
        if (data.type === 'pose-enabled') {
            poseEnabled = Boolean(data.enabled);
            cachedPose=null;poseFrame=0;
            if(poseEnabled) await configureBodyTracking(handsEnabled);
            else { pose?.close(); pose=null; }
            return;
        }
        if (data.type === 'init') {
            handsEnabled = data.handsEnabled !== false;
            poseEnabled = data.poseEnabled !== false;
            preferGPU=data.preferGPU===true;
            trackingBackend = ['mediapipe','leap_motion','nvidia_gpu'].includes(data.backend) ? data.backend : 'mediapipe';
            if (trackingBackend === 'leap_motion') {
                ({mapLeapFrame} = await import('/static/js/tracking-backends.mjs?v=1'));
                await connectLeapMotion();
            }
            const {FilesetResolver, FaceLandmarker: FaceTask, HandLandmarker: HandTask, PoseLandmarker: PoseTask} = await import('/static/vendor/tracking/vision_bundle.mjs?v=2');
            HandLandmarker = HandTask;
            FaceLandmarker = FaceTask;
            PoseLandmarker = PoseTask;
            fileset = await FilesetResolver.forVisionTasks('/static/vendor/tracking/wasm');
            face = await createDetector(FaceTask, {
                baseOptions: {modelAssetPath: '/static/vendor/tracking/face_landmarker.task', delegate: trackingBackend === 'nvidia_gpu' ? 'GPU' : 'CPU'},
                runningMode: 'VIDEO', numFaces: 1, outputFaceBlendshapes: true,
                outputFacialTransformationMatrixes: true,
                minFaceDetectionConfidence:.65,minFacePresenceConfidence:.65,minTrackingConfidence:.65,
            });
            await configureBodyTracking(handsEnabled);
            surface = new OffscreenCanvas(640, 480);
            context = surface.getContext('2d');
            detailSurface=new OffscreenCanvas(512,512);detailContext=detailSurface.getContext('2d');
            self.postMessage({type: 'ready'});
        } else if (data.type === 'frame') {
            try {
                const started=performance.now();
                frameCount++;
                const width=Math.min(Math.max(320,Math.min(960,data.inferenceWidth||960)),data.image.width),height=Math.round(width*data.image.height/data.image.width);
                if(surface.width!==width||surface.height!==height){surface.width=width;surface.height=height;}
                context.drawImage(data.image,0,0,width,height);
                const aspect=data.image.width/data.image.height;
                const bodyEnabled=poseEnabled&&data.bodyTracking!==false;
                const stride=Math.max(1,Math.min(3,data.poseStride||1));
                if(bodyEnabled&&pose&&(!cachedPose||++poseFrame%stride===0))cachedPose=pose.detectForVideo(surface,data.timestamp);
                if(!bodyEnabled)cachedPose=null;
                const p=bodyEnabled?cachedPose:null;
                let roi=faceRegion&&data.timestamp-faceRegionTime<1500?faceRegion:null;
                // A VIDEO detector has temporal state and camera intrinsics.
                // Never switch its input between the camera frame and a crop.
                const full=face.detectForVideo(surface,data.timestamp*2);
                const fullFace=full.faceLandmarks[0]?.length>=468&&full.facialTransformationMatrixes?.[0]?.data?.length===16;
                faceConfirmations=fullFace?Math.min(3,faceConfirmations+1):0;
                const confirmedFace=faceConfirmations>=3;
                let f=full,faceZoomed=false,poseSource='full';
                if(!data.lowLatency&&confirmedFace&&roi&&roi.width<.32&&frameCount%3===0){
                    detailFace ||= await createDetector(FaceLandmarker,{
                    baseOptions:{modelAssetPath:'/static/vendor/tracking/face_landmarker.task',delegate:trackingBackend === 'nvidia_gpu' ? 'GPU' : 'CPU'},
                        runningMode:'VIDEO',numFaces:1,outputFaceBlendshapes:true,outputFacialTransformationMatrixes:true,
                        minFaceDetectionConfidence:.65,minFacePresenceConfidence:.65,minTrackingConfidence:.65,
                    });
                    const detail=detailFace.detectForVideo(detailImage(data.image,roi),data.timestamp*2+1);
                    if(detail.faceLandmarks[0]?.length){
                        detail.faceLandmarks[0]=TrackingDistance.remap(detail.faceLandmarks[0],roi);
                        f=detail;faceZoomed=true;
                        // Crop details improve eyelids/lips, while the full
                        // frame supplies a consistent pose coordinate system.
                        if(full.facialTransformationMatrixes?.[0]?.data)f.facialTransformationMatrixes=full.facialTransformationMatrixes;
                        else poseSource='crop';
                    }
                }
                // Crop detections may refine a confirmed face, never establish
                // or perpetuate presence after the full-frame face disappears.
                const next=confirmedFace?TrackingDistance.faceRegion(full.faceLandmarks[0],p?.landmarks[0],aspect):null;
                if(next){faceRegion=next;faceRegionTime=data.timestamp;}else{faceRegion=null;faceRegionTime=0;}
                const handStride=Math.max(1,Math.min(3,data.handStride||1));
                const updateHands=!cachedHands||frameCount%handStride===0||data.timestamp-cachedHandsAt>100;
                if(!handsEnabled||!bodyEnabled){cachedHands=null;cachedHandsAt=0;}
                let h=trackingBackend === 'leap_motion' && handsEnabled && bodyEnabled
                    ? {landmarks:[],worldLandmarks:[],handedness:[]}
                    : bodyEnabled&&handsEnabled&&hands?(updateHands?hands.detectForVideo(surface,data.timestamp*2):cachedHands):{landmarks:[],worldLandmarks:[],handedness:[]};
                if(bodyEnabled&&handsEnabled&&updateHands){cachedHands=h;cachedHandsAt=data.timestamp;}
                const freshLeapFrame = data.timestamp - leapFrameAt < 500 ? leapFrame : null;
                let leapHands = trackingBackend === 'leap_motion' && bodyEnabled && handsEnabled ? mapLeapFrame(freshLeapFrame, p) : [];
                let handsZoomed=false;
                if(!data.lowLatency&&trackingBackend !== 'leap_motion' && bodyEnabled&&handsEnabled&&hands&&!h.landmarks.length&&frameCount%3===0){
                    const handRoi=TrackingDistance.handRegion(p?.landmarks[0],aspect);
                    if(handRoi){h=hands.detectForVideo(detailImage(data.image,handRoi),data.timestamp*2+1);
                        h.landmarks=h.landmarks.map(points=>TrackingDistance.remap(points,handRoi));handsZoomed=!!h.landmarks.length;}
                }
                const detectedHands = trackingBackend === 'leap_motion' ? leapHands : h.landmarks.map((landmarks, i) => ({landmarks,
                    world: h.worldLandmarks[i], side: h.handedness[i]?.[0]?.categoryName,
                    confidence: h.handedness[i]?.[0]?.score ?? 0}));
                self.postMessage({type: 'result', face: {
                    landmarks: confirmedFace ? f.faceLandmarks[0] || [] : [],
                    blendshapes: confirmedFace ? f.faceBlendshapes[0]?.categories || [] : [],
                    matrix: confirmedFace ? f.facialTransformationMatrixes[0]?.data || null : null,
                    poseSource,
                }, hands: detectedHands,
                pose: p && (confirmedFace || detectedHands.length) ? {landmarks: p.landmarks[0] || [], world: p.worldLandmarks[0] || []} : null,
                handTrackingEnabled: handsEnabled,
                distanceAssist:{faceZoomed,handsZoomed,width,height},
                processingMs:performance.now()-started,timestamp: data.timestamp});
            } finally { data.image.close(); }
        }
    } catch (error) {
        self.postMessage({type: 'error', error: String(error.message || error)});
    }
};

function connectLeapMotion() {
    return new Promise((resolve, reject) => {
        let settled = false;
        const timeout = setTimeout(() => {
            if (settled) return;
            settled = true;
            leapSocket?.close(); leapSocket = null;
            reject(new Error('Leap Motion service was not found at localhost:6437. Connect the controller and start Ultraleap Tracking Service, then retry.'));
        }, 3000);
        try { leapSocket = new WebSocket('ws://127.0.0.1:6437/v6.json'); }
        catch (_) { clearTimeout(timeout); reject(new Error('Could not open the Leap Motion service. Check that Ultraleap Tracking Service is running.')); return; }
        leapSocket.onopen = () => {
            leapConnected = true;
            leapSocket.send(JSON.stringify({background:true}));
            leapSocket.send(JSON.stringify({focused:true}));
            if (!settled) { settled = true; clearTimeout(timeout); resolve(); }
        };
        leapSocket.onmessage = event => {
            try {
                const value = JSON.parse(event.data);
                const frame = value.event?.type === 'tracking_event' ? value.event : value;
                if (Array.isArray(frame.hands)) { leapFrame = frame; leapFrameAt = performance.now(); }
            } catch (_) {}
        };
        leapSocket.onerror = () => {
            if (!settled) { settled = true; clearTimeout(timeout); reject(new Error('Leap Motion connection failed. Start or reinstall Ultraleap Tracking Service and retry.')); }
        };
        leapSocket.onclose = () => {
            leapSocket = null;
            const wasConnected = leapConnected;
            leapConnected = false;
            if (wasConnected) self.postMessage({type:'error',error:'Leap Motion service disconnected. Check the controller and restart tracking.'});
        };
    });
}
