// Classic worker: MediaPipe's WASM loader uses importScripts internally.
let face, detailFace, FaceLandmarker, hands, pose, HandLandmarker, PoseLandmarker, fileset, surface, context, handsEnabled = true;
let handGeneration = 0;
importScripts('/static/js/tracking-distance.js?v=far2');
let detailSurface, detailContext, faceRegion=null, faceRegionTime=0, frameCount=0;
function detailImage(image,roi){
    detailContext.drawImage(image,roi.x*image.width,roi.y*image.height,roi.width*image.width,roi.height*image.height,0,0,512,512);
    return detailSurface;
}

async function configureBodyTracking(enabled) {
    handsEnabled = Boolean(enabled);
    const generation = ++handGeneration;
    if (!handsEnabled) {
        hands?.close(); hands = null;
        pose?.close(); pose = null;
        return;
    }
    if (!fileset) return;
    if (!hands) {
        const detector = await HandLandmarker.createFromOptions(fileset, {
            baseOptions: {modelAssetPath: '/static/vendor/tracking/hand_landmarker.task', delegate: 'CPU'},
            runningMode: 'VIDEO', numHands: 2,
            minHandDetectionConfidence: .7, minHandPresenceConfidence: .7,
            minTrackingConfidence: .65,
        });
        if (generation !== handGeneration || !handsEnabled) { detector.close(); return; }
        hands = detector;
    }
    if (!pose) {
        const detector = await PoseLandmarker.createFromOptions(fileset, {
            baseOptions: {modelAssetPath: '/static/vendor/tracking/pose_landmarker_lite.task', delegate: 'CPU'},
            runningMode: 'VIDEO', numPoses: 1,
            minPoseDetectionConfidence: 0.45, minPosePresenceConfidence: 0.45,
            minTrackingConfidence: 0.45, outputSegmentationMasks: false,
        });
        if (generation !== handGeneration || !handsEnabled) { detector.close(); return; }
        pose = detector;
    }
}

self.onmessage = async ({data}) => {
    try {
        if (data.type === 'hands-enabled') {
            await configureBodyTracking(data.enabled);
            return;
        }
        if (data.type === 'init') {
            handsEnabled = data.handsEnabled !== false;
            const {FilesetResolver, FaceLandmarker: FaceTask, HandLandmarker: HandTask, PoseLandmarker: PoseTask} = await import('/static/vendor/tracking/vision_bundle.mjs?v=2');
            HandLandmarker = HandTask;
            FaceLandmarker = FaceTask;
            PoseLandmarker = PoseTask;
            fileset = await FilesetResolver.forVisionTasks('/static/vendor/tracking/wasm');
            face = await FaceTask.createFromOptions(fileset, {
                baseOptions: {modelAssetPath: '/static/vendor/tracking/face_landmarker.task', delegate: 'CPU'},
                runningMode: 'VIDEO', numFaces: 1, outputFaceBlendshapes: true,
                outputFacialTransformationMatrixes: true,
                minFaceDetectionConfidence:.45,minFacePresenceConfidence:.45,minTrackingConfidence:.45,
            });
            await configureBodyTracking(handsEnabled);
            surface = new OffscreenCanvas(640, 480);
            context = surface.getContext('2d');
            detailSurface=new OffscreenCanvas(512,512);detailContext=detailSurface.getContext('2d');
            self.postMessage({type: 'ready'});
        } else if (data.type === 'frame') {
            try {
                const width=Math.min(960,data.image.width),height=Math.round(width*data.image.height/data.image.width);
                if(surface.width!==width||surface.height!==height){surface.width=width;surface.height=height;}
                context.drawImage(data.image,0,0,width,height);
                const aspect=data.image.width/data.image.height;
                const bodyEnabled=handsEnabled&&data.bodyTracking!==false;
                const p = bodyEnabled && pose ? pose.detectForVideo(surface, data.timestamp) : null;
                let roi=faceRegion&&data.timestamp-faceRegionTime<1500?faceRegion:null;
                // A VIDEO detector has temporal state and camera intrinsics.
                // Never switch its input between the camera frame and a crop.
                const full=face.detectForVideo(surface,data.timestamp*2);
                let f=full,faceZoomed=false,poseSource='full';
                if(roi&&(!full.faceLandmarks[0]?.length||roi.width<.32)){
                    detailFace ||= await FaceLandmarker.createFromOptions(fileset,{
                        baseOptions:{modelAssetPath:'/static/vendor/tracking/face_landmarker.task',delegate:'CPU'},
                        runningMode:'VIDEO',numFaces:1,outputFaceBlendshapes:true,outputFacialTransformationMatrixes:true,
                        minFaceDetectionConfidence:.45,minFacePresenceConfidence:.45,minTrackingConfidence:.45,
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
                let next=TrackingDistance.faceRegion(f.faceLandmarks[0],p?.landmarks[0],aspect);
                if(!next&&!f.faceLandmarks[0]?.length){
                    // Face-only mode has no body landmarks. Search a central
                    // upper-body crop as well as the periodic full frame.
                    const width=.45,height=Math.min(.9,width*aspect);
                    next={x:(1-width)/2,y:Math.max(0,(1-height)*.25),width,height};
                }
                if(next){faceRegion=next;faceRegionTime=data.timestamp;}else if(f.faceLandmarks[0]?.length){faceRegion=null;}
                let h=bodyEnabled&&hands?hands.detectForVideo(surface,data.timestamp*2):{landmarks:[],worldLandmarks:[],handedness:[]};
                let handsZoomed=false;
                if(bodyEnabled&&hands&&!h.landmarks.length){
                    const handRoi=TrackingDistance.handRegion(p?.landmarks[0],aspect);
                    if(handRoi){h=hands.detectForVideo(detailImage(data.image,handRoi),data.timestamp*2+1);
                        h.landmarks=h.landmarks.map(points=>TrackingDistance.remap(points,handRoi));handsZoomed=!!h.landmarks.length;}
                }
                self.postMessage({type: 'result', face: {
                    landmarks: f.faceLandmarks[0] || [],
                    blendshapes: f.faceBlendshapes[0]?.categories || [],
                    matrix: f.facialTransformationMatrixes[0]?.data || null,
                    poseSource,
                }, hands: h.landmarks.map((landmarks, i) => ({landmarks,
                    world: h.worldLandmarks[i], side: h.handedness[i]?.[0]?.categoryName,
                    confidence: h.handedness[i]?.[0]?.score ?? 0})),
                pose: p ? {landmarks: p.landmarks[0] || [], world: p.worldLandmarks[0] || []} : null,
                handTrackingEnabled: handsEnabled,
                distanceAssist:{faceZoomed,handsZoomed,width,height},
                timestamp: data.timestamp});
            } finally { data.image.close(); }
        }
    } catch (error) {
        self.postMessage({type: 'error', error: String(error.message || error)});
    }
};
