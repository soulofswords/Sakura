import {waitForModelGpu} from './model-presentation.js?v=switch85';
import Live2DViewer from './live2d-viewer.js?v=stage-items151';
import ModelBlockTransition from './model-block-transition.js?v=switch85';
import {applyChatReaderLean} from './chat-reader-motion.js?v=1';
import {restoreIdleBreathing,applyIdleBreathing} from './idle-breathing.js?v=2';
import * as THREE from 'three';
import { MMDLoader } from 'three/addons/loaders/MMDLoader.js';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { TGALoader } from 'three/addons/loaders/TGALoader.js';
import { DDSLoader } from 'three/addons/loaders/DDSLoader.js';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { VRMLoaderPlugin, VRMUtils } from '/static/vendor/vrm/three-vrm.module.min.js';
import { UnrealBloomPass } from 'three/addons/postprocessing/UnrealBloomPass.js';
import { FullScreenQuad } from 'three/addons/postprocessing/Pass.js';
import AvatarRetarget from './avatar-retarget.js?v=torso-fluid145';
import ArmClearance from './arm-clearance.js?v=clearance1';
import ModelPhysics from './model-physics.js?v=rest-clearance112';
import ModelRigMonitor from './model-rig-monitor.js?v=authored-cloth76';
import ModelRepairStore from './model-repair-store.js?v=1';
import {ModelBones} from './model-bones.js?v=persistent5';
import {repairNoseSkin} from './pmx-nose-skin.js?v=1';
import ReactionExpressions from './reaction-expressions.js?v=files106';
import {loadVisibility,applyVisibility} from './model-visibility.js?v=irida101';
import ModelDance from './model-dance.js?v=fbx90';
import {classifySpeechGesture,speechGestureWeights} from './speech-gesture.js?v=1';

/**
 * Smart loader for .tga textures.
 * Many anime PMX models label PNG/JPG/BMP textures with .tga extension.
 * This checks file magic bytes and decodes accordingly.
 */
class SmartTgaLoader extends THREE.Loader {
    constructor(manager) {
        super(manager);
        this.tgaLoader = new TGALoader(manager);
        this.ddsLoader = new DDSLoader(manager);
        this.fileLoader = new THREE.FileLoader(manager);
        this.fileLoader.setResponseType('arraybuffer');
    }

    load(url, onLoad, onProgress, onError) {
        const texture = /\.dds(?:\?|$)/i.test(url) ? new THREE.CompressedTexture([], 1, 1) : new THREE.Texture();
        const resolvedUrl = this.manager.resolveURL(url);

        this.fileLoader.load(resolvedUrl, (buffer) => {
            const bytes = new Uint8Array(buffer, 0, Math.min(buffer.byteLength, 8));
            const isPng = bytes[0] === 0x89 && bytes[1] === 0x50 && bytes[2] === 0x4E && bytes[3] === 0x47;
            const isJpg = bytes[0] === 0xFF && bytes[1] === 0xD8 && bytes[2] === 0xFF;
            const isBmp = bytes[0] === 0x42 && bytes[1] === 0x4D;
            const isDds = bytes[0] === 0x44 && bytes[1] === 0x44 && bytes[2] === 0x53 && bytes[3] === 0x20;

            if (isDds) {
                try {
                    const parsed = this.ddsLoader.parse(buffer, true);
                    if (!parsed.width || !parsed.height || !parsed.mipmaps.length) throw new Error('Invalid DDS texture');
                    texture.isCompressedTexture = true;
                    texture.image = {width: parsed.width, height: parsed.height};
                    texture.mipmaps = parsed.mipmaps;
                    texture.format = parsed.format;
                    texture.generateMipmaps = false;
                    texture.needsUpdate = true;
                    if (onLoad) onLoad(texture);
                } catch (error) { if (onError) onError(error); }
                return;
            }

            if (isPng || isJpg || isBmp) {
                // The asset resolver returns a neutral PNG for a missing DDS.
                // Decode the response by its signature rather than its suffix.
                texture.isCompressedTexture = false;
                texture.generateMipmaps = true;
                texture.minFilter = THREE.LinearFilter;
                const mime = isPng ? 'image/png' : isJpg ? 'image/jpeg' : 'image/bmp';
                const blob = new Blob([buffer], { type: mime });
                const blobUrl = URL.createObjectURL(blob);
                this.manager.itemStart(blobUrl);
                const image = new Image();
                image.onload = () => {
                    URL.revokeObjectURL(blobUrl);
                    texture.image = image;
                    texture.needsUpdate = true;
                    if (onLoad) onLoad(texture);
                    this.manager.itemEnd(blobUrl);
                };
                image.onerror = (err) => {
                    URL.revokeObjectURL(blobUrl);
                    if (onError) onError(err);
                    this.manager.itemError(blobUrl);
                    this.manager.itemEnd(blobUrl);
                };
                image.src = blobUrl;
            } else {
                try {
                    const parsed = this.tgaLoader.parse(buffer);
                    // TGALoader.parse returns RGBA bytes, not an image.
                    // A canvas also supports MMDLoader's toon rotation.
                    const canvas = document.createElement('canvas');
                    canvas.width = parsed.width;
                    canvas.height = parsed.height;
                    canvas.getContext('2d').putImageData(new ImageData(
                        new Uint8ClampedArray(parsed.data), parsed.width, parsed.height
                    ), 0, 0);
                    texture.image = canvas;
                    texture.needsUpdate = true;
                    if (onLoad) onLoad(texture);
                } catch (tgaErr) {
                    console.warn(`SmartTgaLoader: TGA parse failed for ${resolvedUrl}:`, tgaErr);
                    if (onError) onError(tgaErr);
                }
            }
        }, onProgress, onError);

        return texture;
    }
}

import {renderPixelRatio} from './render-budget.js?v=startup68';
export default class ModelViewer {
    constructor(containerId) {
        this.container = document.getElementById(containerId);

        // Scene
        this.scene = new THREE.Scene();

        // Camera
        const initialWidth=Math.max(1,this.container.clientWidth||window.innerWidth);
        const initialHeight=Math.max(1,this.container.clientHeight||window.innerHeight);
        this.camera = new THREE.PerspectiveCamera(40, initialWidth / initialHeight, 0.1, 1000);
        this.camera.position.set(0, 14, 18);

        // Renderer
        this.companionSurface = !document.title.startsWith('Sakura VTuber');
        // Windows may fail to create a high-performance, antialiased context
        // after a GPU reset or when the discrete adapter is busy. Retry with
        // progressively less demanding context attributes before giving up;
        // alpha and the retained frame are required by the desktop compositor.
        const rendererOptions = [
            {antialias:true, powerPreference:'high-performance'},
            {antialias:false, powerPreference:'high-performance'},
            {antialias:false, powerPreference:'low-power'},
            {antialias:false, powerPreference:'default'},
        ];
        let rendererError;
        for (const options of rendererOptions) {
            try {
                this.renderer = new THREE.WebGLRenderer({
                    ...options,
                    alpha:true,
                    failIfMajorPerformanceCaveat:false,
                    // Native transparent windows repaint between animation
                    // frames. Retain the last complete compositor frame.
                    preserveDrawingBuffer:true,
                });
                break;
            } catch (error) {
                rendererError = error;
            }
        }
        if (!this.renderer) throw rendererError || new Error('Could not create a WebGL renderer.');
        this.renderer.setDrawingBufferSize(initialWidth,initialHeight,
            renderPixelRatio(initialWidth,initialHeight,Math.min(window.devicePixelRatio,2),this.renderer.capabilities.maxTextureSize));
        Object.assign(this.renderer.domElement.style,{width:'100%',height:'100%'});
        this.renderer.outputColorSpace = THREE.SRGBColorSpace;
        this.renderer.sortObjects = true; // depth-sort transparent draw calls
        this.container.appendChild(this.renderer.domElement);

        // Lights
        this.ambientLight = new THREE.AmbientLight(0xffffff, 1.2);
        this.scene.add(this.ambientLight);

        this.keyLight = new THREE.DirectionalLight(0xfff5f8, 1.4);
        this.keyLight.position.set(5, 20, 15);
        this.scene.add(this.keyLight);
        this.scene.add(this.keyLight.target);

        this.rimLight = new THREE.DirectionalLight(0xff99bb, 0.9);
        this.rimLight.position.set(-8, 15, -10);
        this.scene.add(this.rimLight);

        // Ground / floor atmospheric bounce light
        this.groundLight = new THREE.DirectionalLight(0xff6ea7, 0.4);
        this.groundLight.position.set(0, -6, 6);
        this.scene.add(this.groundLight);
        this.fillLight = new THREE.HemisphereLight(0xf0f5ff, 0x494052, 0.35);
        this.scene.add(this.fillLight);
        this.setQuality(localStorage.getItem('sakura_render_quality') || 'balanced');

        // Environment color state
        this.envColor = '#ff6ea7';
        this.envIntensity = 1.0;
        this.rgbBreathing = false;
        this.onColorChange = null;

        // Controls
        this.controls = new OrbitControls(this.camera, this.renderer.domElement);
        // Direct manipulation should follow the pointer immediately. Orbit
        // damping kept the camera chasing each drag for dozens of frames.
        this.controls.enableDamping = false;
        // OrbitControls' left-pan can lose its gesture in the embedded desktop
        // WebView when the drag crosses canvas bounds. Use our captured pointer
        // path below for mouse panning; retain OrbitControls for right-rotate,
        // wheel zoom and native touch gestures.
        this.renderer.domElement.style.touchAction = 'none';
        this.renderer.domElement.style.cursor = 'default';
        this.controls.target.set(0, 13, 0);
        this.controls.maxPolarAngle = Math.PI / 2 + 0.1;
        this.desktopMode = new URLSearchParams(location.search).has('desktop');
        // Model manipulation is identical in Gemini, Local and VTuber views.
        this._configureModelControls();
        this.renderer.domElement.addEventListener('contextmenu', e => e.preventDefault());
        this.renderer.domElement.addEventListener('dblclick', () => {
            if (this.model) this._autoFrame(this.model);
        });

        // Model state
        this.model = null;
        this.loadGeneration = 0;
        this.animationBones = {};
        this.activity = 'idle';
        this.emotion = 'friendly';
        this.speechLevel = 0;
        this.talkBlend = 0;
        this.thinkBlend = 0;
        this.morphMeshes = []; // meshes with morphTargetDictionary
        this.morphMap = {};    // normalized vowel/blink -> [{ mesh, index }]
        this.allMorphNames = [];
        this.physics = new ModelPhysics();
        this.rigMonitor = new ModelRigMonitor(this);
        this.repairStore = new ModelRepairStore();
        this.reactionExpressions = new ReactionExpressions(this);
        this.dance = new ModelDance(this);
        this.physicsInfo = null;
        this._hairDragVector = new THREE.Vector3();
        this._hairDragAxis = new THREE.Vector3();
        let modelPanPointer = null;
        // Gate OrbitControls and the captured pan path at gesture start.
        // Captured drags can continue outside the silhouette once started.
        this.renderer.domElement.addEventListener('pointerdown',event=>{
            if(!this.controls.enabled)return;
            if(!this._hitModelPixelAt(event.clientX,event.clientY)){
                this.renderer.domElement.style.cursor='default';
                event.stopImmediatePropagation();
                if(event.cancelable)event.preventDefault();
            }
        },{capture:true});
        this.renderer.domElement.addEventListener('pointerdown', event => {
            if (event.button === 0 && this.controls.enabled && event.pointerType !== 'touch') {
                modelPanPointer = {id:event.pointerId, x:event.clientX, y:event.clientY};
                this.renderer.domElement.style.cursor = 'grabbing';
                try { this.renderer.domElement.setPointerCapture(event.pointerId); } catch (_) {}
            }
        });
        this.renderer.domElement.addEventListener('pointermove', event => {
            // Limit synchronous GPU reads for high-polling-rate mice.
            // Cursor gaze still updates on every pointer event; only the drag
            // cursor icon is sampled here. Pointerdown always checks a fresh pixel.
            const hoverNow = performance.now();
            if(!modelPanPointer && event.pointerType!=='touch' &&
                (this._lastHoverPick === undefined || hoverNow-this._lastHoverPick >= 100)) {
                this._lastHoverPick=hoverNow;
                this._updateModelDragCursor(event.clientX,event.clientY);
            }
            if (modelPanPointer?.id === event.pointerId && this.controls.enabled) {
                const dx=event.clientX-modelPanPointer.x,dy=event.clientY-modelPanPointer.y;
                this._panCameraByScreenDelta(dx,dy);
                modelPanPointer.x=event.clientX;modelPanPointer.y=event.clientY;
            }
        });
        for (const type of ['pointerup','pointercancel','lostpointercapture'])
            this.renderer.domElement.addEventListener(type, event => {
                modelPanPointer=null;this._updateModelDragCursor(event.clientX,event.clientY);
            });
        this.renderer.domElement.addEventListener('pointerleave',()=>{if(!modelPanPointer)this.renderer.domElement.style.cursor='default';});
        window.addEventListener('sakura-window-drag', event => {
            this.applyHairScreenDrag(event.detail?.dx,event.detail?.dy);
        });

        // Placeholder avatar when no model is loaded
        this._createPlaceholder();

        // Idle eye blinking
        this.blinkTimer = 0;
        this.nextBlinkTime = 3 + Math.random() * 3;
        this.isBlinking = false;
        this.blinkProgress = 0;
        this.userTracking = false;
        this.trackingMouthEnabled = true;
        this.vtuberTrackingMode = false;
        // Companion mode layers face/hand tracking on top of the AI companion.
        // Unlike VTuber tracking it leaves reactions, choreography and lip-sync on.
        this.companionTracking = false;

        // Event listeners
        this._resizeHandler=()=>this.onResize();
        window.addEventListener('resize', this._resizeHandler);

        // Start animation loop
        this.clock = new THREE.Clock();
        this.animate = this.animate.bind(this);
        this.animationFrame=requestAnimationFrame(this.animate);
    }

    destroy() {
        if(this.destroyed)return;
        this.destroyed=true;
        if(this.animationFrame)cancelAnimationFrame(this.animationFrame);
        this._cursorPickTarget?.dispose();
        window.removeEventListener('resize',this._resizeHandler);
        this._disposeLive2D();
        if(this.model)this._disposeObject(this.model);
        if(this.placeholderGroup)this._disposeObject(this.placeholderGroup);
        this.physics?.detach?.();
        this.renderer?.dispose?.();
        this.renderer?.domElement?.remove?.();
    }

    _createPlaceholder() {
        this.placeholderGroup = new THREE.Group();

        // Glowing anime crystal/core orb
        const geo = new THREE.IcosahedronGeometry(2.2, 3);
        const mat = new THREE.MeshStandardMaterial({
            color: 0xff6ea7,
            emissive: 0xaa2055,
            roughness: 0.2,
            metalness: 0.8,
            wireframe: true,
        });
        this.placeholderMesh = new THREE.Mesh(geo, mat);
        this.placeholderMesh.position.set(0, 13, 0);
        this.placeholderGroup.add(this.placeholderMesh);

        // Inner soft core
        const innerGeo = new THREE.SphereGeometry(1.4, 32, 32);
        const innerMat = new THREE.MeshBasicMaterial({ color: 0xffaacc });
        this.innerOrb = new THREE.Mesh(innerGeo, innerMat);
        this.innerOrb.position.set(0, 13, 0);
        this.placeholderGroup.add(this.innerOrb);

        this.scene.add(this.placeholderGroup);
    }

    _configureModelControls() {
        this.controls.screenSpacePanning = true;
        // Left mouse panning is handled explicitly with pointer capture in the
        // constructor, avoiding lost drags in pywebview/Chromium surfaces.
        this.controls.mouseButtons.LEFT = -1;
        this.controls.mouseButtons.RIGHT = THREE.MOUSE.ROTATE;
        this.controls.touches.ONE = THREE.TOUCH.PAN;
    }

    _updateModelDragCursor(x,y) {
        const picking=document.body.classList.contains('model-part-picking')||document.body.classList.contains('picking-model-part');
        this.renderer.domElement.style.cursor=picking?'':this.controls.enabled&&!document.body.classList.contains('studio-model-locked')&&this._hitModelPixelAt(x,y)?'grab':'default';
    }

    _hitModelPixelAt(x,y) {
        if(!this.model || this._displayLoading)return false;
        const renderer=this.renderer,rect=renderer.domElement.getBoundingClientRect();
        if(!rect.width||!rect.height||x<rect.left||y<rect.top||x>=rect.right||y>=rect.bottom)return false;
        // A one-pixel view of the model uses GPU skinning and the original
        // texture alpha. CPU raycasting skins every triangle of every mesh.
        this._cursorPickTarget ||= new THREE.WebGLRenderTarget(1,1,{depthBuffer:true});
        this._cursorPickTarget.texture.colorSpace=renderer.outputColorSpace;
        this._cursorPickCamera ||= this.camera.clone();
        const camera=this._cursorPickCamera;
        camera.copy(this.camera,false);
        camera.setViewOffset(rect.width,rect.height,x-rect.left,y-rect.top,1,1);
        const priorTarget=renderer.getRenderTarget();
        const priorViewport=renderer.getViewport(this._cursorPickViewport ||= new THREE.Vector4()).clone();
        const priorScissor=renderer.getScissor(this._cursorPickScissor ||= new THREE.Vector4()).clone();
        const priorScissorTest=renderer.getScissorTest(),priorAlpha=renderer.getClearAlpha();
        const priorColor=renderer.getClearColor(this._cursorPickColor ||= new THREE.Color()).clone();
        const background=this.scene.background,hidden=[];
        try {
            for(const child of this.scene.children)if(child!==this.model&&!child.isLight&&child.visible){hidden.push(child);child.visible=false;}
            this.scene.background=null;
            renderer.setRenderTarget(this._cursorPickTarget);
            renderer.setViewport(0,0,1,1);
            renderer.setScissorTest(false);
            renderer.setClearColor(0,0);
            renderer.clear();
            renderer.render(this.scene,camera);
            const pixel=this._cursorPickPixel ||= new Uint8Array(4);
            renderer.readRenderTargetPixels(this._cursorPickTarget,0,0,1,1,pixel);
            return pixel[3]>5;
        } finally {
            for(const child of hidden)child.visible=true;
            this.scene.background=background;
            renderer.setRenderTarget(priorTarget);
            renderer.setViewport(priorViewport);
            renderer.setScissor(priorScissor);
            renderer.setScissorTest(priorScissorTest);
            renderer.setClearColor(priorColor,priorAlpha);
        }
    }

    _hitModelAt(x,y) {
        if(!this.model || this._displayLoading)return false;
        const rect=this.renderer.domElement.getBoundingClientRect();
        if(!rect.width||!rect.height)return false;
        this.model.updateMatrixWorld(true);this.camera.updateMatrixWorld(true);
        this.model.traverse(object=>{if(object.isSkinnedMesh)object.computeBoundingSphere?.();});
        this._dragRay ||= new THREE.Raycaster();
        this._dragPointer ||= new THREE.Vector2();
        this._dragPointer.set((x-rect.left)/rect.width*2-1,-(y-rect.top)/rect.height*2+1);
        this._dragRay.setFromCamera(this._dragPointer,this.camera);
        return this._dragRay.intersectObject(this.model,true).some(hit=>{
            for(let node=hit.object;node;node=node.parent)if(node.visible===false)return false;
            const material=Array.isArray(hit.object.material)?hit.object.material[hit.face?.materialIndex??0]:hit.object.material;
            return material && material.visible!==false && (material.opacity??1)>.02;
        });
    }

    _panCameraByScreenDelta(dx,dy) {
        if(!Number.isFinite(dx)||!Number.isFinite(dy)||(!dx&&!dy))return;
        const height=Math.max(1,this.renderer.domElement.clientHeight||this.container.clientHeight);
        const distance=this.camera.position.distanceTo(this.controls.target);
        const worldPerPixel=2*distance*Math.tan(THREE.MathUtils.degToRad(this.camera.fov)*0.5)/height;
        this.camera.updateMatrixWorld();
        const right=new THREE.Vector3().setFromMatrixColumn(this.camera.matrixWorld,0);
        const up=new THREE.Vector3().setFromMatrixColumn(this.camera.matrixWorld,1);
        const offset=right.multiplyScalar(-dx*worldPerPixel).addScaledVector(up,dy*worldPerPixel);
        this.camera.position.add(offset);
        this.controls.target.add(offset);
        this.controls.update();
    }

    _holdPresentedFrame() {
        // An alpha snapshot replaces the live canvas (CSS hides it), so it
        // is safe on native Companion windows too. Do not stack it above the
        // model-switch animation, which already owns a complete saved frame.
        if (this.blockTransition?.canvas) return;
        if (this._heldFrame || this._displayLoading || !this.model) return;
        const source = this.live2d?.app?.view || this.renderer.domElement;
        if (!source?.width || !source?.height) return;
        // WebGL's default drawing buffer is discarded after presentation.
        // Render and copy in the same task, before releasing the old model.
        this._renderFrame();
        const frame = document.createElement('canvas');
        frame.className = 'model-held-frame';
        frame.width = source.width; frame.height = source.height;
        frame.getContext('2d').drawImage(source, 0, 0);
        Object.assign(frame.style, {position:'absolute', inset:'0', width:'100%', height:'100%', pointerEvents:'none', zIndex:'1'});
        this.container.appendChild(frame);
        this._heldFrame = frame;
        // Alpha snapshots cannot cover a live alpha canvas: both characters
        // remain visible wherever the old frame is transparent. Replace the
        // source surface until the new frame can be presented atomically.
        this.container.classList?.add('model-frame-held');
    }

    _releasePresentedFrame(ticket) {
        const frame = this._heldFrame;
        if (!frame) return;
        // Keep the copy through one compositor frame. A stale load must not
        // remove the snapshot belonging to a later model selection.
        requestAnimationFrame(() => requestAnimationFrame(() => {
            if (ticket !== this._displayLoadTicket || this._displayLoading || this._modelPresentationPending === ticket) return;
            frame.remove();
            if (this._heldFrame === frame) {
                this._heldFrame = null;
                this.container.classList?.remove('model-frame-held');
            }
        }));
    }

    onResize() {
        this.live2d?.fit();
        if (this.resizeFrame) return;
        this.resizeFrame = requestAnimationFrame(() => {
            this.resizeFrame = null;
            const width = Math.max(1, this.container.clientWidth||window.innerWidth);
            const height = Math.max(1, this.container.clientHeight||window.innerHeight);
            this.camera.aspect = width / height;
            this.camera.updateProjectionMatrix();
            if (this._displayLoading) return;
            if (this.live2d) { this._renderFrame(); return; }
            const current = this.renderer.getSize(this._resizeSize ||= new THREE.Vector2());
            // Setting canvas dimensions clears its drawing buffer even when
            // unchanged. Native layout notifications can repeat one size.
            if (current.x !== width || current.y !== height) {
                if (!this.live2d) this._holdPresentedFrame();
                const scale={low:.75,balanced:1.25,high:2}[this.quality]||1;
                this.renderer.setDrawingBufferSize(width,height,
                    renderPixelRatio(width,height,Math.min(window.devicePixelRatio*scale,3),this.renderer.capabilities.maxTextureSize));
                this._resizeBloom();
            }
            this._renderFrame();
            if (!this.live2d) this._releasePresentedFrame(this._displayLoadTicket);
        });
    }

    setDisplaySize(percent) {
        const value = Number(percent);
        // Keep a sensible lower bound, but allow wheel zoom to grow past the
        // old 180% ceiling so users can zoom in as far as they need.
        this.camera.zoom = Math.max(0.4, Number.isFinite(value) ? value / 100 : 1);
        this.camera.updateProjectionMatrix();
        localStorage.setItem('sakura_model_size', String(Math.round(this.camera.zoom * 100)));
        this.live2d?.fit();
    }

    setQuality(mode) {
        const presets = {
            low: { scale: 0.75, anisotropy: 1, ambient: 0.9, key: 1.35, fill: 0.25 },
            balanced: { scale: 1.25, anisotropy: 4, ambient: 0.9, key: 1.35, fill: 0.25 },
            high: { scale: 2, anisotropy: 16, ambient: 0.9, key: 1.35, fill: 0.25 },
        };
        this.quality = presets[mode] ? mode : 'balanced';
        const preset = presets[this.quality];
        // While loading, retain the last presented frame and defer canvas
        // reallocations until the next model is fully ready.
        if (this.live2d && !this._displayLoading) { this.live2d.fit();localStorage.setItem('sakura_render_quality',this.quality);return; }
        if (this._displayLoading) {
            localStorage.setItem('sakura_render_quality', this.quality);
            return;
        }
        const width = Math.max(1, this.container.clientWidth||window.innerWidth), height = Math.max(1, this.container.clientHeight||window.innerHeight);
        const ratio = renderPixelRatio(width,height,Math.min(window.devicePixelRatio*preset.scale,3),this.renderer.capabilities.maxTextureSize);
        this._holdPresentedFrame();
        this.camera.aspect = width / height;
        this.camera.updateProjectionMatrix();
        const current = this.renderer.getSize(new THREE.Vector2());
        if (this.renderer.getPixelRatio() !== ratio || current.x !== width || current.y !== height)
            this.renderer.setDrawingBufferSize(width, height, ratio);
        this.ambientLight.intensity = preset.ambient;
        this.keyLight.intensity = preset.key;
        this.fillLight.intensity = preset.fill;
        const anisotropy = Math.min(preset.anisotropy, this.renderer.capabilities.getMaxAnisotropy());
        this.model?.traverse(child => {
            const materials = Array.isArray(child.material) ? child.material : [child.material];
            for (const material of materials) {
                if (!material) continue;
                for (const texture of Object.values(material)) {
                    if (texture?.isTexture && texture.anisotropy !== anisotropy) {
                        texture.anisotropy = anisotropy;
                        texture.needsUpdate = true;
                    }
                }
            }
        });
        localStorage.setItem('sakura_render_quality', this.quality);
        this.setCharacterGlow(this.characterGlow ?? Number(localStorage.getItem('sakura_character_glow') || 0));
        this.setLightAngles(Number(localStorage.getItem('sakura_light_angle') || 35), Number(localStorage.getItem('sakura_light_elevation') || 30));
        this.setGlossBoost(Number(localStorage.getItem('sakura_gloss_boost') || 0));
        this._resizeBloom();
        if (this.clock && this.controls) this._renderFrame();
        this._releasePresentedFrame(this._displayLoadTicket);
    }

    _disposeObject(root) {
        if (this.armClearance?.root === root) this.armClearance = null;
        if (!root) return;
        root.removeFromParent();
        const resources = new Set();
        root.traverse((child) => {
            if (child.geometry) resources.add(child.geometry);
            if (child.skeleton) resources.add(child.skeleton);
            const materials = Array.isArray(child.material) ? child.material : [child.material];
            for (const material of materials) {
                if (!material) continue;
                resources.add(material);
                for (const value of Object.values(material)) {
                    if (value?.isTexture) resources.add(value);
                }
                for (const uniform of Object.values(material.uniforms || {})) {
                    if (uniform.value?.isTexture) resources.add(uniform.value);
                }
            }
        });
        for (const resource of resources) resource.dispose();
        this.renderer.renderLists.dispose();
        // Disposing a model invalidates its vertex/texture bindings. Reset the
        // cached GL state before the next model/overlay frame on ANGLE.
        this.renderer.resetState?.();
    }

    _validatePmxReferences(data) {
        if (data.metadata.format !== 'pmx') return data;
        const morphs = data.morphs.map(morph => {
            let elements = morph.elements;
            if (morph.type === 0) elements = elements.filter(e => Number.isInteger(e.index) && e.index >= 0 && e.index < data.morphs.length && Number.isFinite(e.ratio));
            if (morph.type === 8) elements = elements.filter(e => e.index === -1 || (e.index >= 0 && e.index < data.materials.length));
            return {...morph, elements, elementCount: elements.length};
        });
        // Broken rigid-body/joint references must not crash MMDLoader before
        // the spring solver can use the skeleton's name-based fallback.
        const bodies = data.rigidBodies || [];
        const constraints = data.constraints || [];
        const brokenRig = bodies.some(body => !body || !Number.isInteger(body.boneIndex)
            || body.boneIndex < -1 || body.boneIndex >= (data.bones?.length || 0)
            || ![0, 1, 2].includes(body.type)
            || [body.position, body.rotation].some(values => values && (!Array.isArray(values) || !values.every(Number.isFinite))))
            || constraints.some(joint => !joint || [joint.rigidBodyIndex1, joint.rigidBodyIndex2]
                .some(index => !Number.isInteger(index) || index < 0 || index >= bodies.length));
        if (brokenRig) return {...data, morphs, rigidBodies: [], constraints: [],
            metadata: {...data.metadata, rigidBodyCount: 0, constraintCount: 0}};
        return {...data, morphs};
    }

    _preparePmxMorphData(data) {
        if (data.metadata.format !== 'pmx') return data;
        const vertices = data.metadata.vertexCount;
        const width = this.renderer.capabilities?.maxTextureSize || 4096;
        const bytesPerMorph = Math.ceil(vertices / width) * width * 16;
        const gl = this.renderer.getContext?.();
        const layers = gl ? gl.getParameter(gl.MAX_ARRAY_TEXTURE_LAYERS) : 256;
        const limit = Math.max(0, Math.min(64, layers || 256, Math.floor(64 * 1024 * 1024 / Math.max(1, bytesPerMorph))));
        if (data.morphs.length <= limit) return data;
        const aliases = [
            ['あ', 'a', 'A', 'mouth_a', 'Mouth_A', 'mouthOpen', 'jawOpen'],
            ['い', 'i', 'I', 'mouth_i', 'Mouth_I'], ['う', 'u', 'U', 'mouth_u', 'Mouth_U'],
            ['え', 'e', 'E', 'mouth_e', 'Mouth_E'], ['お', 'o', 'O', 'mouth_o', 'Mouth_O'],
            ['まばたき', 'blink', 'Blink', '目_まばたき'], ['にこり', '笑い'], ['困る'], ['真面目']
        ];
        // Flatten group expressions using their original indices before selecting
        // a subset. This keeps composite vowels intact without dense copies of
        // every underlying face/teeth/tongue morph.
        const flatten = (index, weight, result, visiting) => {
            if (visiting.has(index) || !Number.isFinite(weight)) return;
            const morph = data.morphs[index];
            if (!morph) return;
            if (morph.type === 1) {
                for (const element of morph.elements) {
                    if (element.index < 0 || element.index >= vertices || !element.position.every(Number.isFinite)) continue;
                    const value = result.get(element.index) || [0, 0, 0];
                    for (let axis = 0; axis < 3; axis++) value[axis] += element.position[axis] * weight;
                    result.set(element.index, value);
                }
            } else if (morph.type === 0) {
                const next = new Set(visiting); next.add(index);
                for (const element of morph.elements) flatten(element.index, weight * element.ratio, result, next);
            }
        };
        const chosen = [];
        const used = new Set();
        const add = index => {
            if (index < 0 || used.has(index) || chosen.length >= limit) return;
            used.add(index);
            const offsets = new Map(); flatten(index, 1, offsets, new Set());
            if (!offsets.size) return;
            const elements = [...offsets].map(([index, position]) => ({index, position}));
            chosen.push({...data.morphs[index], type: 1, elements, elementCount: elements.length});
        };
        for (const names of aliases) {
            const index = names.map(name => data.morphs.findIndex(m => m.name === name)).find(i => i >= 0);
            if (index !== undefined) add(index);
        }
        for (let i = 0; i < data.morphs.length && chosen.length < limit; i++) add(i);
        this.pendingMorphBudget = `Memory-safe model: using ${chosen.length} of ${data.morphs.length} morphs, prioritizing speech and blinking.`;
        console.info(this.pendingMorphBudget);
        return {...data, metadata: {...data.metadata, morphCount: chosen.length}, morphs: chosen};
    }

    _sanitizeGeometry(root) {
        let invalidVertices = 0;
        root.traverse(child => {
            const geometry = child.geometry;
            const position = geometry?.attributes?.position;
            // MMDLoader writes position: [] for accessories without morphs.
            // Three enables USE_MORPHTARGETS for a present attribute, but emits
            // no MORPHTARGETS_COUNT for zero entries: the vertex shader fails.
            for (const [name, targets] of Object.entries(geometry?.morphAttributes || {})) {
                if (Array.isArray(targets) && targets.length === 0) delete geometry.morphAttributes[name];
            }
            if (!position) return;
            // Corrupt exports can contain coordinates in the thousands that
            // still pass the absolute 10,000-unit check. Estimate the model's
            // own scale from its median vertex radius rather than these tails.
            const radii = [];
            const sampleStep = Math.max(1, Math.floor(position.count / 2048));
            for (let i = 0; i < position.count; i += sampleStep) {
                const radius = Math.hypot(position.getX(i), position.getY(i), position.getZ(i));
                if (Number.isFinite(radius)) radii.push(radius);
            }
            radii.sort((a, b) => a - b);
            const radiusLimit = Math.min(10000, Math.max(100, (radii[Math.floor(radii.length / 2)] || 2) * 50));
            const invalid = new Set();
            for (let i = 0; i < position.count; i++) {
                const coordinates = [position.getX(i), position.getY(i), position.getZ(i)];
                if (coordinates.some(n => !Number.isFinite(n)) || Math.hypot(...coordinates) > radiusLimit) invalid.add(i);
            }
            // Some MMD exports also carry non-finite values in morph targets.
            // They do not show up in the base vertex audit, but become visible
            // as spikes as soon as an expression is applied.
            for (const morph of geometry.morphAttributes.position || []) {
                for (let i = 0; i < morph.count; i++) {
                    const values = [morph.getX(i), morph.getY(i), morph.getZ(i)];
                    if (values.some(n => !Number.isFinite(n)) || Math.hypot(...values) > radiusLimit) {
                        morph.setXYZ(i,
                            geometry.morphTargetsRelative ? 0 : position.getX(Math.min(i, position.count - 1)),
                            geometry.morphTargetsRelative ? 0 : position.getY(Math.min(i, position.count - 1)),
                            geometry.morphTargetsRelative ? 0 : position.getZ(Math.min(i, position.count - 1)));
                        morph.needsUpdate = true;
                    }
                }
            }
            invalidVertices += invalid.size;
            if (!invalid.size) return;
            let replacement = 0;
            while (invalid.has(replacement) && replacement < position.count) replacement++;
            if (replacement === position.count) return;
            for (const vertex of invalid) {
                position.setXYZ(vertex, position.getX(replacement), position.getY(replacement), position.getZ(replacement));
                for (const morph of geometry.morphAttributes.position || []) {
                    morph.setXYZ(vertex,
                        geometry.morphTargetsRelative ? 0 : position.getX(replacement),
                        geometry.morphTargetsRelative ? 0 : position.getY(replacement),
                        geometry.morphTargetsRelative ? 0 : position.getZ(replacement));
                    morph.needsUpdate = true;
                }
            }
            // Keep material group offsets, but collapse invalid triangles.
            const index = geometry.index;
            if (index) {
                for (let i = 0; i < index.count; i += 3) {
                    if ([index.getX(i), index.getX(i + 1), index.getX(i + 2)].some(n => invalid.has(n))) {
                        index.setX(i, replacement);
                        index.setX(i + 1, replacement);
                        index.setX(i + 2, replacement);
                    }
                }
                index.needsUpdate = true;
            }
            position.needsUpdate = true;
            geometry.computeBoundingBox();
            geometry.computeBoundingSphere();
            // SkinnedMesh caches separate bounds used by Box3 and culling.
            if ('boundingBox' in child) child.boundingBox = null;
            if ('boundingSphere' in child) child.boundingSphere = null;
        });
        return { invalidVertices };
    }

    _disposeLive2D() {
        this.live2d?.destroy();this.live2d=null;
        this.renderer.domElement.style.visibility='visible';
    }
    async _loadLive2D(url) {
        const generation=++this.loadGeneration;
        const loaded=await Live2DViewer.create(url,this);
        if(generation!==this.loadGeneration){loaded.destroy();return null;}
        this._disposeLive2D();this._disposeObject(this.model);this._disposeObject(this.placeholderGroup);
        this.placeholderGroup=null;this.placeholderMesh=null;this.innerOrb=null;
        this.physics.detach();this.vrm=null;this.model=new THREE.Group();this.live2d=loaded;
        this.animationBones={};this.morphMap={};this.morphMeshes=[];this.resolvedVowels={A:'A',I:'I',U:'U',E:'E',O:'O',Blink:'Blink'};this.pmxTextureSlots=[];
        this.allMorphNames=loaded.names;this.physicsInfo=loaded.physicsInfo;
        this.renderer.domElement.style.visibility='hidden';
        // PIXI owns the visible surface now; release the unused 3D framebuffer.
        // setQuality restores its dimensions when a 3D model is loaded again.
        this.renderer.setDrawingBufferSize(1,1,1);
        loaded.render(1/60);
        return {model:this.model,morphs:this.allMorphNames,physics:this.physicsInfo,notice:'Live2D loaded. Hand movement depends on authored parameters; generic 3D arm tracking is not applied.'};
    }

    async loadModel(url, options = {}) {
        this.blockTransition ||= new ModelBlockTransition(this);
        const transitionHoldsFrame=this.blockTransition.begin();
        // The running camera worker must never retarget the disposed skeleton.
        // Rebuild the retargeter for the new format after the load completes.
        const resumeTracking = this.userTracking || this._resumeTrackingOnLoad;
        this._resumeTrackingOnLoad = resumeTracking;
        if (this.userTracking) this.setUserTracking(false, {preserveIntent:true});
        this.boneControls=null;
        this.physics.disabledBones=new Set();
        this.userTrackingSample = null;
        this.dance?.stop(true);
        this.reactionExpressions?.clear();
        if(!transitionHoldsFrame)this._holdPresentedFrame();
        this.materialEditor?.restore();
        const ticket = (this._displayLoadTicket || 0) + 1;
        this._displayLoadTicket = ticket;
        this.clearManualExpression();
        this._displayLoading = true;
        try {
            const result=await this._loadModelInternal(url, options);
            if(result&&ticket===this._displayLoadTicket){
                this.lastModelUrl=url;
                loadVisibility(this,url);
                // Imported skinned bounds describe the bind pose. Moving
                // hair/skirts can escape those cached bounds during dragging.
                this.model?.traverse(child=>{if(child.isSkinnedMesh)child.frustumCulled=false;});
                if(!this.live2d){
                    await this.repairStore.load(url,()=>ticket===this._displayLoadTicket&&!!this.model);
                    if(ticket!==this._displayLoadTicket)return null;
                }
                this.rigMonitor?.start(url);
                if(!this.live2d)this.boneControls=new ModelBones(this,this.repairStore.key(url));
            }
            return result;
        } finally {
            if (ticket === this._displayLoadTicket) {
                this._modelPresentationPending = ticket;
                this._displayLoading = false;
                this._applyTrackingRestPose();
                if (resumeTracking && this.model && this.userTrackingRequested!==false) this.setUserTracking(true);
                this._resumeTrackingOnLoad = false;
                // Present the fully framed model in this task, before the
                // compositor can show a cleared canvas between frames.
                this.setQuality(this.quality);
                // Final quality/gloss changes can invalidate textures/programs
                // after the loader's first compile. Keep the previous image
                // through the final draw and its GPU uploads.
                try{await this._finishModelPresentation(ticket);}
                finally{
                    if(ticket===this._displayLoadTicket){
                        this._modelPresentationPending = null;
                        this._releasePresentedFrame(ticket);
                        void this.blockTransition.reveal();
                    }
                }
            }
        }
    }

    async _finishModelPresentation(ticket){
        if(this.live2d||!this.model||!this.renderer?.getContext)return;
        const current=()=>ticket===this._displayLoadTicket&&!this._displayLoading;
        await this.renderer.compileAsync(this.scene,this.camera);
        if(!current())return;
        this._renderFrame();
        const ready=await waitForModelGpu(this.renderer,current);
        if(!ready&&current())console.warn('Model presentation GPU wait did not complete; context lost or GPU busy.');
    }

    async _loadModelInternal(url, options = {}) {
        // A lighting target belongs to the model whose material was picked.
        this.characterLightingTarget = null;
        this._bloomTargetObjects = [];
        if (/\.model3\.json(?:\?|$)/i.test(url)) return this._loadLive2D(url);
        this.humanoidInfo = null;
        const isVrm = /\.vrm(?:\?|$)/i.test(url);
        // Keep all PMX imports on the stable spring solver from their first
        // frame. A malformed Bullet rig can otherwise move bones visibly
        // before the runtime jitter guard has enough samples to react.
        this.physics.forceSpring = !isVrm && options.forceSpring !== false;
        this.physics.forceSpringReason = options.forceSpringReason
            || (this.physics.forceSpring ? 'Safe spring-chain physics is active for PMX rigs to prevent unstable rigid-body motion.' : '');
        if (isVrm) return this._loadVrm(url);
        this.physics.glitchFixPolicy = ['auto', 'on', 'off'].includes(options.glitchFixPolicy) ? options.glitchFixPolicy : 'auto';
        this.vrm = null;
        this.textureReview = null;
        this.humanoidInfo = null;
        this.isRacingOutfitModel = /大凤赛车服2\.4/i.test(decodeURIComponent(url));
        const started = performance.now();
        const report = stage => window.pywebview?.api.model_load_status(stage, (performance.now() - started) / 1000);
        report('fetch');
        const generation = ++this.loadGeneration;
        // Remove and release the previous character before starting the next.
        this._disposeObject(this.model);
        this.model = null;
        this.animationBones = {};
        this.morphMeshes = [];
        this.morphMap = {};
        this.allMorphNames = [];
        this.physicsInfo = null;
        this.physics.detach();
        this.resolvedVowels = {};
        this.blinkTimer = 0;
        this.isBlinking = false;
        this.blinkProgress = 0;
        if (this.placeholderGroup) {
            this._disposeObject(this.placeholderGroup);
            this.placeholderGroup = null;
            this.placeholderMesh = null;
            this.innerOrb = null;
        }

        // Determine model directory
        const lastSlash = url.lastIndexOf('/');
        const modelDir = lastSlash !== -1 ? url.substring(0, lastSlash + 1) : '';

        // Check if textures.json exists for this model
        let textureMap = {};
        let preserveAuthoredMaterials = false;
        let materialTextures = {};
        this.pmxTextureSlots = [];
        try {
            const res = await fetch(`${modelDir}textures.json`, {cache: 'no-store'});
            if (res.ok) {
                const data = await res.json();
                materialTextures = data.materials?.[decodeURIComponent(url.substring(lastSlash + 1))] || {};
                preserveAuthoredMaterials = data.preserve_materials === true;
                if (data.textures) {
                    textureMap = data.textures;
                    console.log('📄 Found textures.json mapping for model:', Object.keys(textureMap).length, 'entries');
                }
            }
        } catch (_) {}
        if (generation !== this.loadGeneration) return null;

        // Setup custom LoadingManager for MMDLoader
        const manager = new THREE.LoadingManager();
        // MMDLoader returns the mesh before its images finish decoding.
        // Wait for those images so alpha flags and shader inputs are final.
        const assetsReady = new Promise(resolve => { manager.onLoad = resolve; });

        // Handle .tga files with SmartTgaLoader
        manager.addHandler(/\.tga$/i, new SmartTgaLoader(manager));
        manager.addHandler(/\.dds$/i, new SmartTgaLoader(manager));

        const assetRoles = new Map();
        let textureReview = null;
        // URL rewrite handler: normalize backslashes & apply textures.json
        manager.setURLModifier((requestedUrl) => {
            let clean = requestedUrl.replace(/\\/g, '/');

            // Check if mapped in textures.json
            for (const [srcKey, mappedRel] of Object.entries(textureMap)) {
                const normKey = srcKey.replace(/\\/g, '/');
                if (clean.endsWith(normKey) || clean.endsWith(encodeURI(normKey)) || clean.endsWith(srcKey)) {
                    clean = `${modelDir}${mappedRel.replace(/\\/g, '/')}`;
                    break;
                }
            }
            for (const [filename, role] of assetRoles) {
                const name = filename.replace(/\\/g, '/');
                if (clean.endsWith(name) || clean.endsWith(encodeURI(name))) {
                    clean += (clean.includes('?') ? '&' : '?') + 'fallback=' + role;
                    break;
                }
            }
            return clean;
        });

        manager.onError = (itemUrl) => {
            console.warn('⚠️ Asset warning during model load:', itemUrl);
        };

        return new Promise((resolve, reject) => {
            const loader = new MMDLoader(manager);
            // Bound allocation before MMDLoader creates dense vertex arrays.
            if (loader.meshBuilder) {
                const buildMesh = loader.meshBuilder.build.bind(loader.meshBuilder);
                loader.meshBuilder.build = (data, ...args) => {
                    data = this._validatePmxReferences(data);
                    this.pmxTextureSlots = this._applyPmxTextureOverrides(data, materialTextures);
                    for (const material of data.materials || []) {
                        const sphere = data.textures?.[material.envTextureIndex];
                        if (sphere && material.envFlag) assetRoles.set(sphere, material.envFlag === 1 ? 'white' : 'black');
                    }
                    for (const material of data.materials || []) {
                        const diffuse = data.textures?.[material.textureIndex];
                        if (diffuse) assetRoles.set(diffuse, 'white');
                    }
                    for (const material of data.materials || []) {
                        const toon = material.toonFlag === 0 && data.textures?.[material.toonIndex];
                        if (toon && !assetRoles.has(toon)) assetRoles.set(toon, 'white');
                    }
                    if (modelDir.startsWith('/models/')) {
                        // Check the same repaired reference that the image loader uses.
                        const pathFor = name => {
                            const normalized = name.replace(/\\/g, '/');
                            const entry = Object.entries(textureMap).find(([key]) => key.replace(/\\/g, '/') === normalized);
                            return decodeURIComponent(modelDir.slice(8)) + (entry?.[1] || name).replace(/\\/g, '/');
                        };
                        const diffuse = new Set((data.materials || []).map(m=>data.textures?.[m.textureIndex]).filter(Boolean));
                        const paths = [...assetRoles.keys()].map(pathFor);
                        const diffusePaths = new Set([...diffuse].map(pathFor));
                        const optional_paths = [...assetRoles.keys()].map(pathFor).filter(path=>!diffusePaths.has(path));
                        textureReview = fetch('/api/models/texture-check', {method: 'POST', signal: AbortSignal.timeout(5000), headers: {'Content-Type': 'application/json'},
                            body: JSON.stringify({paths, optional_paths})}).then(r => r.ok ? r.json() : null).catch(() => null);
                    }
                    const mesh = buildMesh(this._validatePmxReferences(data), ...args);
                    for (const [i, material] of (Array.isArray(mesh.material) ? mesh.material : [mesh.material]).entries()) {
                        if (!material) continue;
                        material.userData ||= {};
                        material.userData.MMD ||= {};
                        material.userData.MMD.userToonOverride = !!materialTextures[i]?.toon;
                        material.userData.MMD.userSphereOverride = !!materialTextures[i]?.sphere;
                    }
                    return mesh;
                };
            }
            const geometryBuilder = loader.meshBuilder?.geometryBuilder;
            let memoryNotice = null;
            if (geometryBuilder) {
                const build = geometryBuilder.build.bind(geometryBuilder);
                geometryBuilder.build = data => {
                    this.pendingMorphBudget = null;
                    const prepared = this._preparePmxMorphData(data);
                    memoryNotice = this.pendingMorphBudget;
                    return build(prepared);
                };
            }

            loader.load(
                url,
                async (mmd) => {
                    report('textures');
                    let geometryRepairs;
                    // An older request may finish after another selection.
                    if (generation !== this.loadGeneration) {
                        this._disposeObject(mmd);
                        resolve(null);
                        return;
                    }
                    // Prepare GPU shaders before displaying the character.
                    // Parallel compilation avoids blocking the first frame.
                    try {
                        this.humanoidInfo = this._validatePmxHumanoid(mmd);
                        geometryRepairs = this._sanitizeGeometry(mmd);
                        await assetsReady;
                        const review = await textureReview;
                        if (generation !== this.loadGeneration) {
                            this._disposeObject(mmd); resolve(null); return;
                        }
                        this.textureReview = review;
                        // Texture failures use the authored material path until
                        // the user compares the exact file in PMX Editor.
                        this.pmxReferenceMode = !!(review?.required_missing ?? review?.missing)?.length || preserveAuthoredMaterials || !!this.preferPmxReference || !!(textureReview && !review);
                        // Keep comparison available as an explicit action.
                        // Missing optional shine maps must not launch an
                        // external editor or switch the entire material mode.
                        if (generation !== this.loadGeneration) {
                            this._disposeObject(mmd); resolve(null); return;
                        }
                        if (!this.pmxReferenceMode) this._fixPairedSurfaceMaterials(mmd);
                        // MMDLoader discovers texture transparency only after
                        // image decoding. Apply it to the material before shaders
                        // compile, otherwise eye highlights become opaque white.
                        this._preparePmxMaterials(mmd);
                        repairNoseSkin(mmd);
                        this._repairDancerSkirtAtlas(mmd);
                        this._fixPmxLayeredSurfaces(mmd);
                        await this.physics.initialize?.(mmd);
                        report('shaders');
                        if (generation !== this.loadGeneration) {
                            this._disposeObject(mmd);
                            resolve(null);
                            return;
                        }
                        await this.renderer.compileAsync(mmd, this.camera, this.scene);
                        this._checkModelShaders(mmd);
                    } catch (err) {
                        this._disposeObject(mmd);
                        if (generation !== this.loadGeneration) resolve(null);
                        else reject(err);
                        return;
                    }
                    if (generation !== this.loadGeneration) {
                        this._disposeObject(mmd);
                        resolve(null);
                        return;
                    }
                    try {
                        this._disposeLive2D();
                        this.model = mmd;
                        this.setQuality(this.quality);
                        this.scene.add(this.model);

                        // Scan meshes for morph targets
                        this._indexMorphTargets(this.model);
                        this._setupCharacterAnimation(this.model);
                        // Run the model's own physics rig (hair, clothing, body)
                        // through Bullet, with spring fallback, after gesture bones are
                        // indexed so they stay out of the fallback detection.
                        const reserved = new Set(Object.values(this.animationBones).map(e => e.bone.name));
                        // A cleanup choice belongs to a specific model path;
                        // never let the previous avatar's choice affect this rig.
                        this.physicsInfo = this.physics.attach(this.model, reserved);

                        // Frame upper body / face
                        this._autoFrame(this.model);
                    } catch (err) {
                        // A failure while indexing the loaded model must still
                        // settle the load promise and release the character.
                        this.model = null;
                        this.physicsInfo = null;
                        this.physics.detach();
                        this._disposeObject(mmd);
                        if (generation === this.loadGeneration) reject(err);
                        else resolve(null);
                        return;
                    }

                    console.log('✅ Model loaded successfully. Found morphs:', this.allMorphNames);
                    console.info(`Model ready in ${((performance.now() - started) / 1000).toFixed(2)}s`);
                    report('ready');
                    resolve({
                        model: this.model,
                        morphs: this.allMorphNames,
                        physics: this.physicsInfo,
                        humanoid: this.humanoidInfo,
                        notice: [(this.textureReview?.required_missing ?? this.textureReview?.missing)?.length ? 'Missing diffuse texture references. Use Check textures in PMX Editor to inspect them.' : this.textureReview?.optional_missing?.length ? `${this.textureReview.optional_missing.length} optional shine maps missing; neutral fallbacks used.` : null, memoryNotice, geometryRepairs?.invalidVertices ? `Removed ${geometryRepairs.invalidVertices} invalid vertices. A complete re-export may be needed for missing geometry.` : null].filter(Boolean).join(" ") || null,
                    });
                },
                (xhr) => {
                    if (xhr.total) {
                        const percent = Math.round((xhr.loaded / xhr.total) * 100);
                        console.log(`Loading 3D model: ${percent}%`);
                    }
                },
                (err) => {
                    report('error');
                    if (generation !== this.loadGeneration) {
                        resolve(null);
                        return;
                    }
                    console.error('Failed to load MMD model:', err);
                    reject(err);
                }
            );
        });
    }

    _checkModelShaders(root) {
        const gl = this.renderer.getContext?.();
        if (!gl || !this.renderer.properties) return;
        root.traverse(child => {
            for (const material of (Array.isArray(child.material) ? child.material : [child.material])) {
                if (!material) continue;
                const program = this.renderer.properties.get(material).currentProgram?.program;
                if (program && !gl.getProgramParameter(program, gl.LINK_STATUS)) {
                    const detail = gl.getProgramInfoLog(program) || 'GPU shader linking failed';
                    console.error(`Model shader failed (${material.name || material.type}): ${detail}`);
                    throw new Error(`The GPU could not render material "${material.name || material.type}". Try Low quality or a re-exported model.`);
                }
            }
        });
    }

    async _loadVrm(url) {
        this.humanoidInfo = null;
        const generation = ++this.loadGeneration;
        const loader = new GLTFLoader();
        loader.register(parser => new VRMLoaderPlugin(parser));
        const gltf = await loader.loadAsync(url);
        const vrm = gltf.userData.vrm;
        if (!vrm) { this._disposeObject(gltf.scene); throw new Error('The file does not contain a VRM avatar.'); }
        if (generation !== this.loadGeneration) { this._disposeObject(vrm.scene); return null; }
        const requiredHumanoidBones = ['hips', 'spine', 'head', 'leftUpperArm', 'rightUpperArm', 'leftUpperLeg', 'rightUpperLeg'];
        const missingHumanoidBones = requiredHumanoidBones.filter(name => !vrm.humanoid?.getNormalizedBoneNode(name));
        if (missingHumanoidBones.length) {
            this._disposeObject(vrm.scene);
            throw new Error(`This VRM does not contain a complete humanoid rig (missing ${missingHumanoidBones.join(', ')}). Import a humanoid VRM avatar.`);
        }
        this.humanoidInfo = {format:'VRM', groups: requiredHumanoidBones.slice()};
        // Avatar authors compress look-at into a few degrees (this rig allows
        // 8/12), which makes cursor tracking invisible; widen the output range.
        const lookAtApplier = vrm.lookAt?.applier;
        // Expression maps produce 0..1 weights, not degrees. Enlarging those
        // to 30 saturates the pupils and makes these VRMs appear unresponsive.
        if (lookAtApplier && !lookAtApplier.expressions && lookAtApplier.constructor?.type !== 'expression') {
            for (const key of ['rangeMapHorizontalInner', 'rangeMapHorizontalOuter', 'rangeMapVerticalDown', 'rangeMapVerticalUp']) {
                if (lookAtApplier[key]) lookAtApplier[key].outputScale = 30;
            }
        }
        VRMUtils.rotateVRM0(vrm);
        // VRM uses meters; the existing MMD stage uses larger model units.
        vrm.scene.scale.setScalar(10);
        this.setGlossBoost(Number(localStorage.getItem('sakura_gloss_boost') || 0), vrm.scene);
        try { await this.renderer.compileAsync(vrm.scene, this.camera, this.scene); }
        catch (error) { this._disposeObject(vrm.scene); throw error; }
        if (generation !== this.loadGeneration) { this._disposeObject(vrm.scene); return null; }
        this._disposeLive2D();
        this._disposeObject(this.model);
        this._disposeObject(this.placeholderGroup);
        this.placeholderGroup = null;
        this.model = vrm.scene;
        this.vrm = vrm;
        this.textureReview = null;
        this.scene.add(this.model);
        this._indexMorphTargets(this.model);
        this._setupCharacterAnimation(this.model);
        for (const [key, name] of Object.entries({ torso: 'spine', chest: 'chest', head: 'head', neck: 'neck', leftEye: 'leftEye', rightEye: 'rightEye', leftArm: 'leftUpperArm', rightArm: 'rightUpperArm', leftElbow: 'leftLowerArm', rightElbow: 'rightLowerArm', leftWrist: 'leftHand', rightWrist: 'rightHand',leftThigh:'leftUpperLeg',rightThigh:'rightUpperLeg',leftKnee:'leftLowerLeg',rightKnee:'rightLowerLeg' })) {
            const bone = vrm.humanoid?.getNormalizedBoneNode(name);
            if (bone) this.animationBones[key] = { bone, rest: bone.rotation.clone() };
        }
        this._indexVrmExpressions();
        this.allMorphNames = Object.keys(vrm.expressionManager?.expressionMap || {});
        this.physicsInfo = this.physics.attachVrm(this.vrm);
        this._vrmJointRest = null;
        this._syncVrmPhysics();
        this.blinkTimer = 0;
        this.isBlinking = false;
        this.setQuality(this.quality);
        // Refresh skin matrices after converting VRM meters to stage units.
        // Cached bounds from loading/compilation otherwise frame an empty area.
        this.vrm.update(0);
        this.model.updateMatrixWorld(true);
        this.model.traverse(child => {
            if (!child.isSkinnedMesh) return;
            child.skeleton.update();
            child.computeBoundingBox();
            child.computeBoundingSphere();
        });
        this._autoFrame(this.model);
        return { model: this.model, morphs: this.allMorphNames, humanoid: this.humanoidInfo };
    }

    _validatePmxHumanoid(root) {
        const mmdBones = [];
        root.traverse(child => {
            if (!child.isSkinnedMesh) return;
            const bones = child.geometry?.userData?.MMD?.bones;
            if (Array.isArray(bones) && bones.length) mmdBones.push(...bones);
        });
        const names = mmdBones.flatMap(bone => [bone?.name, bone?.englishName]).filter(Boolean)
            .map(name => String(name).toLowerCase().replace(/^(?:mixamorig|armature|bip\d*)[._ :\-]*/, '').replace(/[\s_.:\-]+/g, ''));
        const has = pattern => names.some(name => pattern.test(name));
        const groups = {
            hips: has(/^(?:センター|中|腰|下半身|骨盤|髋骨|髋|胯|全ての親|hips?|pelvis|root|lowerbody)$/i),
            torso: has(/^(?:上半身\d*|上身|胸|躯干|脊柱|spine\d*|chest|torso|upperbody)$/i),
            head: has(/^(?:頭|头|頭部|头部|head)$/i),
            leftArm: has(/^(?:左(?:肩|肩膀|腕|上臂|手臂|小臂|前臂|ひじ|肘|手)|(?:left|l)(?:shoulder|upperarm|arm|forearm|lowerarm|elbow|hand)|(?:upperarm|arm|forearm|lowerarm|elbow|hand)(?:left|l))$/i),
            rightArm: has(/^(?:右(?:肩|肩膀|腕|上臂|手臂|小臂|前臂|ひじ|肘|手)|(?:right|r)(?:shoulder|upperarm|arm|forearm|lowerarm|elbow|hand)|(?:upperarm|arm|forearm|lowerarm|elbow|hand)(?:right|r))$/i),
            leftLeg: has(/^(?:左(?:足|脚|腿|もも|ひざ|膝|足首|大腿|小腿|脚踝)|(?:left|l)(?:upperleg|leg|thigh|lowerleg|calf|foot|ankle)|(?:upperleg|leg|thigh|lowerleg|calf|foot|ankle)(?:left|l))$/i),
            rightLeg: has(/^(?:右(?:足|脚|腿|もも|ひざ|膝|足首|大腿|小腿|脚踝)|(?:right|r)(?:upperleg|leg|thigh|lowerleg|calf|foot|ankle)|(?:upperleg|leg|thigh|lowerleg|calf|foot|ankle)(?:right|r))$/i),
        };
        const labels = {hips:'hips/pelvis', torso:'spine/torso', head:'head', leftArm:'left arm', rightArm:'right arm', leftLeg:'left leg', rightLeg:'right leg'};
        const missing = Object.keys(groups).filter(group => !groups[group]);
        if (missing.length) throw new Error(`This PMX does not have a recognizable humanoid skeleton (missing ${missing.map(group => labels[group]).join(', ')}). Import a humanoid PMX avatar.`);
        return groups;
    }

    _indexVrmExpressions() {
        const manager = this.vrm?.expressionManager;
        this.resolvedVowels = {};
        const aliases = { A: ['aa', 'a'], I: ['ih', 'i'], U: ['ou', 'u'],
            E: ['ee', 'e'], O: ['oh', 'o'], Blink: ['blink'] };
        for (const [key, names] of Object.entries(aliases)) {
            const name = names.find(name => manager?.getExpression(name));
            if (name) this.resolvedVowels[key] = name;
        }
    }

    _indexMorphTargets(root) {
        this.morphMeshes = [];
        this.morphMap = {};
        const morphNameSet = new Set();

        root.traverse((child) => {
            if (child.isMesh && child.morphTargetDictionary && child.morphTargetInfluences) {
                this.morphMeshes.push(child);
                for (const [name, index] of Object.entries(child.morphTargetDictionary)) {
                    morphNameSet.add(name);
                    if (!this.morphMap[name]) {
                        this.morphMap[name] = [];
                    }
                    this.morphMap[name].push({ mesh: child, index });
                }
            }
        });

        this.allMorphNames = Array.from(morphNameSet);

        // Japanese & Western Vowel Mappings
        const aliases = {
            'A': ['あ', 'a', 'A', 'ああ', '口_あ', 'mouth_a', 'Mouth_A', 'mouthOpen', 'jawOpen'],
            'I': ['い', 'i', 'I', '口_い', 'mouth_i', 'Mouth_I'],
            'U': ['う', 'u', 'U', '口_う', 'mouth_u', 'Mouth_U'],
            'E': ['え', 'e', 'E', '口_え', 'mouth_e', 'Mouth_E'],
            'O': ['お', 'o', 'O', '口_お', 'mouth_o', 'Mouth_O'],
            'Blink': ['まばたき', 'blink', 'Blink', '目_まばたき', 'ウィンク'],
        };

        this.resolvedVowels = {};
        for (const [vowel, list] of Object.entries(aliases)) {
            for (const alias of list) {
                if (this.morphMap[alias]) {
                    this.resolvedVowels[vowel] = alias;
                    break;
                }
            }
        }
        console.log('Resolved Vowel Morph Targets:', this.resolvedVowels);
    }

    _setupCharacterAnimation(root) {
        this.armClearance = null;
        this.animationBones = {};
        this.conversationMotion = null;
        this.conversationFingers = [];
        const aliases = {
            torso: ['上半身', 'spine', 'Spine'],
            chest: ['上半身2', 'chest', 'Chest'],
            head: ['頭', 'head', 'Head'],
            neck: ['首', 'neck', 'Neck'],
            leftEye: ['左目', 'LeftEye', 'eye.L', 'leftEye', 'Eye_L', 'eye_l', 'J_Adj_L_FaceEye', 'mixamorigLeftEye'],
            rightEye: ['右目', 'RightEye', 'eye.R', 'rightEye', 'Eye_R', 'eye_r', 'J_Adj_R_FaceEye', 'mixamorigRightEye'],
            leftShoulder: ['左肩', '左肩P', '左鎖骨', '左锁骨', 'LeftShoulder', 'LeftClavicle', 'mixamorigLeftShoulder', 'shoulder.L', 'clavicle.L', 'clavicleLeft'],
            rightShoulder: ['右肩', '右肩P', '右鎖骨', '右锁骨', 'RightShoulder', 'RightClavicle', 'mixamorigRightShoulder', 'shoulder.R', 'clavicle.R', 'clavicleRight'],
            leftWrist: ['左手首', 'LeftHand', 'hand.L'],
            rightWrist: ['右手首', 'RightHand', 'hand.R'],
            leftArm: ['左腕', 'LeftArm', 'upper_arm.L'],
            rightArm: ['右腕', 'RightArm', 'upper_arm.R'],
            leftElbow: ['左ひじ', 'LeftForeArm', 'forearm.L'],
            rightElbow: ['右ひじ', 'RightForeArm', 'forearm.R'],
            leftThigh: ['左足','左腿','LeftLeg','LeftUpLeg','thigh.L'],
            rightThigh: ['右足','右腿','RightLeg','RightUpLeg','thigh.R'],
            leftKnee: ['左ひざ','左膝','LeftKnee','LeftLowerLeg','shin.L'],
            rightKnee: ['右ひざ','右膝','RightKnee','RightLowerLeg','shin.R'],
        };
        root.traverse(child => {
            if (!child.isBone) return;
            for (const [key, names] of Object.entries(aliases)) {
                if (names.includes(child.name) && !this.animationBones[key]) {
                    this.animationBones[key] = { bone: child, rest: child.rotation.clone() };
                }
            }
        });
        for (const side of ['left', 'right']) {
            const key = side + 'Shoulder';
            const bone = this.vrm?.humanoid?.getNormalizedBoneNode(side + 'Shoulder');
            if (bone && !this.animationBones[key]) this.animationBones[key] = {bone, rest: bone.rotation.clone()};
        }
        const fingerNames = ['Thumb', 'Index', 'Middle', 'Ring', 'Little'];
        const japanese = ['親指', '人指', '中指', '薬指', '小指'];
        const digits = ['０', '１', '２', '３'];
        for (const side of ['left', 'right']) for (let finger = 0; finger < 5; finger++) for (let segment = 0; segment < 3; segment++) {
            const index = finger === 0 ? segment : segment + 1;
            let bone = this.vrm?.humanoid?.getNormalizedBoneNode(side + fingerNames[finger] +
                (finger === 0 ? ['Metacarpal', 'Proximal', 'Distal'] : ['Proximal', 'Intermediate', 'Distal'])[segment]);
            if (!bone) root.traverse(child => {
                if (child.isBone && [(side === 'left' ? '左' : '右') + japanese[finger] + index,
                    (side === 'left' ? '左' : '右') + japanese[finger] + digits[index],
                    (side === 'left' ? 'Left' : 'Right') + fingerNames[finger] + (segment + 1)].includes(child.name)) bone = child;
            });
            if (bone) this.conversationFingers.push({bone, side, finger, segment, rest: bone.rotation.clone(), curl: 0});
        }
        const facialAliases = { smile: ['にこり'], concern: ['困る'], focus: ['真面目'] };
        this.expressionMorphs = {};
        for (const [key, names] of Object.entries(facialAliases)) {
            this.expressionMorphs[key] = names.find(name => this.morphMap[name]);
        }
        this.expressionWeights = { smile: 0, concern: 0, focus: 0 };
    }

    _applyPmxTextureOverrides(data, materialTextures) {
        const slots = [];
        const fields = {diffuse: 'textureIndex', sphere: 'envTextureIndex', toon: 'toonIndex'};
        for (const [i, material] of (data.materials || []).entries()) {
            for (const [slot, field] of Object.entries(fields)) {
                const original = slot === 'toon' && material.toonFlag !== 0
                    ? `Shared toon ${material.toonIndex + 1}` : data.textures?.[material[field]] || '(none)';
                const chosen = materialTextures[i]?.[slot];
                slots.push({material:i, name:material.name, slot, original, chosen:chosen || null});
                if (typeof chosen === 'string' && chosen && !chosen.startsWith('/') && !chosen.split(/[\\/]/).includes('..') && !chosen.includes(':')) {
                    material[field] = data.textures.push(chosen) - 1;
                    if (slot === 'toon') material.toonFlag = 0;
                    if (slot === 'sphere' && !material.envFlag) material.envFlag = 1;
                }
            }
        }
        return slots;
    }

    _preparePmxMaterials(root) {
        const materialNames = new Set();
        let racingBodyMaterial = null;
        const authoredTextureNames = new Set();
        root.traverse(child => {
            const materials = Array.isArray(child.material) ? child.material : [child.material];
            for (const material of materials) {
                if (!material?.name) continue;
                materialNames.add(material.name);
                authoredTextureNames.add(String(material.userData?.MMD?.mapFileName || material.map?.name || '').replace(/\\/g, '/').toLowerCase());
                if (material.name === 'cf_m_body') racingBodyMaterial = material;
            }
        });
        const racingOutfitProfile = this.isRacingOutfitModel || (
            [...materialNames].some(name => /^cf_m_shorts_06\b/i.test(name)) &&
            [...materialNames].some(name => /^kurisu_jacket\b/i.test(name)) &&
            materialNames.has('qipaox2')
        );
        const anantaRichieProfile = materialNames.has('f脸') &&
            materialNames.has('a身体皮肤') && materialNames.has('a腰挂宠');
        const princessProfile = materialNames.has('Clothes - Top Crystal') &&
            materialNames.has('body03') && materialNames.has('face01');
        const nanallyProfile = [...authoredTextureNames].some(name => /(?:^|\/)player_010_nanally_hair_01_d\.tga$/.test(name))
            && [...authoredTextureNames].some(name => /(?:^|\/)t_player_010_nanally_face_d\.tga$/.test(name));
        const shenheProfile = ['颜', '肌', '肌2', '髪spa+', '神之眼AL'].every(name => materialNames.has(name));
        // This qipao port uses traditional hair names and a separate highlight pass.
        const shenheQipaoProfile = ['髮', '髮+', '肌2', '裙内'].every(name => materialNames.has(name))
            && [...authoredTextureNames].some(name => /(?:^|\/)spa_h\.png$/i.test(name));
        // Casual Miku's facial expression cards share the same "face" name
        // and are authored at 0.99 opacity. Treating them as blended cards
        // disables depth writes, so the blue sphere region in face.png draws
        // over the skin. PMXView treats these as opaque facial layers.
        const casualMikuFaceProfile = materialNames.has('face')
            && [...authoredTextureNames].some(name => /(?:^|\/)face_mikuap_b\.tga$/i.test(name))
            && [...authoredTextureNames].some(name => /(?:^|\/)face\.png$/i.test(name));
        this.isShenheQipaoModel = shenheQipaoProfile;
        this.isRacingOutfitModel = racingOutfitProfile;
        root.traverse(child => {
            for (const material of (Array.isArray(child.material) ? child.material : [child.material])) {
                if (!material) continue;
                if (!material.isMMDToonMaterial) continue;
                // Large generic PMX garment panels often share a cutout atlas
                // with tiny ornaments. The atlas-wide alpha flag must not turn
                // the solid garment into a transparent accessory surface.
                const materialIndex = Array.isArray(child.material) ? child.material.indexOf(material) : 0;
                const panelIndices = (child.geometry?.groups || []).filter(g => g.materialIndex === materialIndex)
                    .reduce((sum, g) => sum + g.count, 0);
                const solidPanel = material.opacity >= .999 && panelIndices >= 6000
                    && /^(?:材質[0-9]*|material[0-9]*)$/iu.test(material.name || '');
                if (casualMikuFaceProfile && material.name === 'face' &&
                    /(?:^|\\|\/)face(?:_mikuap_b)?\.(?:tga|png)$/i.test(material.userData?.MMD?.mapFileName || '')) {
                    // These are stacked face/eye/mouth expression cards, not
                    // translucent glass. Preserve opaque depth ordering.
                    material.opacity = 1;
                    material.transparent = false;
                    material.alphaTest = 0;
                    material.depthWrite = true;
                }
                const textureCutout = material.map?.transparent === true && material.opacity >= 0.999;
                if (material.map?.transparent === true) material.transparent = true;
                if (textureCutout) {
                    material.alphaTest = Math.max(material.alphaTest || 0, 0.01);
                    material.depthWrite = true;
                }
                // MMD alpha morphs mark solid faces as transparent even at
                // rest. Keep their depth so hidden expression cards/back hair
                // cannot draw through the face. Genuine translucency still blends.
                // PMX commonly uses 0.98/0.99 for otherwise solid layered
                // faces, hair and clothing. Keep their depth like PMXView;
                // disabling it reveals back surfaces through the front layer.
                // Model profiles below and saved user overrides retain priority.
                if (material.transparent && !textureCutout) material.depthWrite = material.opacity >= .98;
                if (solidPanel) {
                    material.transparent = false;
                    material.alphaTest = 0;
                    material.depthWrite = true;
                }
                const hairMapFile = String(material.userData?.MMD?.mapFileName || material.map?.name || '').replace(/\\/g, '/');
                const taffyHair = /^f头发(?:[23])?$/u.test(material.name || '') && /(?:^|\/)taffy_hair_color\.png$/i.test(hairMapFile)
                    && material.opacity >= .999;
                if (taffyHair) {
                    // This atlas's soft alpha made solid bangs see-through.
                    // Cut out strand gaps, then draw surviving hair opaque so
                    // both the face and the desktop stay behind its surface.
                    material.transparent = false;
                    material.alphaTest = Math.max(material.alphaTest || 0, .2);
                    material.depthWrite = true;
                }
                if (shenheQipaoProfile && material.name === '髮') {
                    // Retain the source hair ramp's cool silver shadow tint under
                    // the bright companion stage, instead of clipping to white.
                    material.diffuse?.setRGB(0.86, 0.89, 0.93);
                    material.color?.setRGB(0.86, 0.89, 0.93);
                }
                // Haku's long-hair shell is authored at 0.99 alpha, but still
                // needs depth writes. Its main outfit uses the atlas as opaque
                // artwork; auto-detected atlas alpha exposes the body beneath.
                const hakuOffice = [...authoredTextureNames].some(n => /(?:^|\/)hair_hakuap\.tga$/i.test(n))
                    && [...authoredTextureNames].some(n => /(?:^|\/)white_d\.png$/i.test(n));
                if (hakuOffice) {
                    const mapName = String(material.userData?.MMD?.mapFileName || '').replace(/\\/g, '/');
                    if (/hair_hakuap\.tga$/i.test(mapName)) {
                        material.depthWrite = true;
                        material.alphaTest = Math.max(material.alphaTest || 0, 0.01);
                    }
                    if (material.name === '材質1' && /white_d\.png$/i.test(mapName)) {
                        material.transparent = false;
                        material.depthWrite = true;
                        material.alphaTest = 0;
                    }
                }
                if (this.pmxReferenceMode || princessProfile || nanallyProfile) {
                    // Keep PMX diffuse, ambient, toon, sphere and sidedness
                    // settings. MMD's ambient term must use the same diffuse
                    // atlas; otherwise Three adds an untextured grey veil.
                    if (material.map) material.emissiveMap = material.map;
                    // This export relies on authored ambient to fill its toon
                    // shadows. MMDLoader attenuates textured ambient by .2;
                    // recover it without whitening the diffuse artwork.
                    if (nanallyProfile && material.map && !material.userData.MMD.nanallyAmbientRestored) {
                        material.emissive.multiplyScalar(5);
                        material.userData.MMD.nanallyAmbientRestored = true;
                    }
                    material.blending = THREE.NormalBlending;
                    material.needsUpdate = true;
                    continue;
                }
                const racingAlphaClothing = racingOutfitProfile && /^cf_m_shorts_06\b/i.test(material.name || '');
                if (racingAlphaClothing) {
                    // This atlas is mostly transparent. MMD treats it as a
                    // cutout, while an opaque Three material turns the empty
                    // pixels into solid shorts and hides the bikini beneath.
                    material.transparent = true;
                    material.alphaTest = 0.01;
                    material.depthWrite = true;
                }
                if (racingOutfitProfile && (material.name || '') === '新規' && racingBodyMaterial?.map) {
                    // Despite its generic name this is lower-body skin, not a
                    // clothing overlay. The PMX omits its duplicate texture
                    // reference, so reuse the matching cf_m_body atlas.
                    material.map = racingBodyMaterial.map;
                    material.gradientMap = racingBodyMaterial.gradientMap;
                }
                // MMD ambient light is not an untextured white overlay. Tint
                // the ambient contribution with the diffuse texture as well.
                if (material.map) {
                    const mapFileName = String(
                        material.userData?.MMD?.mapFileName || material.map?.name || ''
                    ).replace(/\\/g, '/');
                    const isAnantaFaceMaterial =
                        /^(?:L-基础脸|f脸|脸-基础脸|g脸)$/iu.test(material.name || '') ||
                        (/(?:meikanika|richie|linqin|taffy)_face_color\.png$/i.test(mapFileName) &&
                            /(?:脸|顔|(?:^|_)face(?:$|_))/iu.test(material.name || ''));
                    const isAnantaRichieSkin = anantaRichieProfile &&
                        /^(?:a身体皮肤|c手指皮肤)$/u.test(material.name || '');
                    const isPrincessSkin = princessProfile &&
                        /(?:^|\/)(?:body(?:00|02)_MikuAp(?:_b)?\.tga|face_MikuAp_b fixed\.png)$/i.test(mapFileName);
                    const isShenheSkin = shenheProfile && /^(?:颜|肌)[12]?$/u.test(material.name || '');
                    // This racing outfit was authored for MMD's dimmer ambient
                    // light. Applying its diffuse map a second time as emission
                    // bleaches the skin and turns the clothing highlights white.
                    material.emissiveMap = racingOutfitProfile ? null : material.map;
                    const diffuse = material.diffuse;
                    if (diffuse && diffuse.r > .1 && Math.abs(diffuse.r - diffuse.g) < .002 && Math.abs(diffuse.r - diffuse.b) < .002) {
                        // Many game ports store an old renderer's grey lighting
                        // compensation in diffuse. It darkens the face independently
                        // of a correctly colored body texture in this renderer.
                        diffuse.setRGB(1, 1, 1);
                    }
                    // The princess export uses numbered skin names (body03,
                    // face01) that do not match the generic skin-name rule.
                    // Its toon ramp darkens the torso independently of the face.
                    if (!material.userData?.MMD?.userToonOverride && (isPrincessSkin || isAnantaFaceMaterial || isAnantaRichieSkin)) {
                        // Game face toon ramps assume the original engine's
                        // face-light uniforms. Use the stage's neutral ramp for
                        // skin instead of baking an unrelated dark face shadow.
                        material.gradientMap = null;
                    }
                    // An authored skin ramp may be almost white, with subtle
                    // warm shading. Removing it invokes Three's hard two-band
                    // fallback, producing polygon-shaped grey shoulder patches.
                    // Preserve it for every other model, including numbered skin.
                    const ambient = material.emissive;
                    if (ambient && Math.abs(ambient.r - ambient.g) < .002 && Math.abs(ambient.r - ambient.b) < .002) {
                        const faceFill = racingOutfitProfile ? .015
                            : (isAnantaFaceMaterial || isAnantaRichieSkin) ? .68
                            : (isPrincessSkin || isShenheSkin) ? .35
                            : /(?:脸|顔|(?:^|_)face(?:$|_))/iu.test(material.name || '') ? .35 : .06;
                        ambient.setRGB(faceFill, faceFill, faceFill);
                    }
                    if (racingOutfitProfile && /(?:cf_m_body|body 2)/i.test(material.userData?.MMD?.mapFileName || '')) {
                        // The bundled body atlas has nearly-white base pixels.
                        // MMD normally warms those through its material pass;
                        // reproduce that tint under Three's physically brighter
                        // stage so skin remains peach rather than paper white.
                        material.color?.setRGB(1.0, 0.79, 0.72);
                        material.diffuse?.setRGB(1.0, 0.79, 0.72);
                    }
                    if (racingOutfitProfile && /^(?:Face|FacePart)\.002$/i.test(material.name || '')) {
                        // This port's face atlas expects the same warm MMD
                        // material tint as its body. Without it, the face is
                        // rendered grey while the neck and torso stay peach.
                        material.color?.setRGB(1.0, 0.79, 0.72);
                        material.diffuse?.setRGB(1.0, 0.79, 0.72);
                    }
                }
                // Full additive sphere maps overwhelm diffuse colors under
                // modern lighting. Keep the highlight, with a bounded strength.
                if (!material.userData?.MMD?.userSphereOverride) material.fragmentShader = material.fragmentShader.replace(
                    'outgoingLight += matcapColor.rgb;',
                    'outgoingLight += matcapColor.rgb * 0.12;');
                // Standard source-over preserves opaque faces on alpha windows.
                material.blending = THREE.NormalBlending;
                material.needsUpdate = true;
            }
        });
    }

    _fixPairedSurfaceMaterials(root) {
        // Some PMX exports include a separate, reverse-wound back surface.
        // Rendering both copies double-sided makes their opposite normals
        // fight at exactly the same depth. Each copy should show its front.
        root.traverse(child => {
            const materials = Array.isArray(child.material) ? child.material : [];
            const byName = new Map(materials.map(material => [material.name, material]));
            for (const back of materials) {
                if (!back.name?.endsWith('+')) continue;
                const front = byName.get(back.name.slice(0, -1));
                if (!front || front.map !== back.map) continue;
                const geometry = child.geometry;
                const positions = geometry?.attributes?.position;
                const indices = geometry?.index;
                const frontGroup = geometry?.groups?.find(group => group.materialIndex === materials.indexOf(front));
                const backGroup = geometry?.groups?.find(group => group.materialIndex === materials.indexOf(back));
                if (!positions || !indices || !frontGroup || !backGroup) continue;
                // A '+' name alone does not prove a reverse surface. Only
                // cull confirmed coincident triangles with opposite winding.
                const vertex = i => [positions.getX(i), positions.getY(i), positions.getZ(i)].map(n => n.toFixed(5)).join(',');
                const triangle = (offset, reverse = false) => {
                    const points = [vertex(indices.getX(offset)), vertex(indices.getX(offset + 1)), vertex(indices.getX(offset + 2))];
                    if (reverse) [points[1], points[2]] = [points[2], points[1]];
                    return [points.join('|'), [points[1], points[2], points[0]].join('|'), [points[2], points[0], points[1]].join('|')].sort()[0];
                };
                const fronts = new Set();
                for (let i = frontGroup.start; i < frontGroup.start + frontGroup.count; i += 3) fronts.add(triangle(i));
                let checked = 0, matched = 0;
                const step = Math.max(1, Math.ceil(backGroup.count / 3 / 128)) * 3;
                for (let i = backGroup.start; i < backGroup.start + backGroup.count; i += step) {
                    checked++; if (fronts.has(triangle(i, true))) matched++;
                }
                if (!checked || matched / checked < .95) continue;
                front.side = THREE.FrontSide;
                back.side = THREE.FrontSide;
                front.needsUpdate = back.needsUpdate = true;
            }
        });
    }

    _repairDancerSkirtAtlas(root) {
        // Scoped runtime atlas repair; original PMX and texture files stay intact.
        // This dress contains skirt vertices sampling unrelated transparent atlas regions.
        root.traverse(mesh => {
            if (!Array.isArray(mesh.material)) return;
            const index=mesh.material.findIndex(m=>m.name==='Profissional Do Sexo Dress'
                && /(?:^|[\\/])5\.png$/i.test(m.userData?.MMD?.mapFileName||''));
            const g=mesh.geometry, p=g?.attributes?.position, uv=g?.attributes?.uv, ix=g?.index;
            if(index<0||!p||!uv||!ix) return;
            const group=g.groups.find(g=>g.materialIndex===index); if(!group)return;
            const visited=new Set();
            for(let o=group.start;o<group.start+group.count;o++) {
                const i=ix.getX(o);if(visited.has(i))continue;visited.add(i);
                const y=p.getY(i);if(y>=15.35)continue;
                uv.setXY(i,.905+THREE.MathUtils.clamp((p.getX(i)+1.25)/2.5,0,1)*.085,
                    .787+THREE.MathUtils.clamp((15.35-y)/3.3,0,1)*.055);
            }
            uv.needsUpdate=true;
        });
    }

    _fixPmxLayeredSurfaces(root) {
        // Transparent decals can share every triangle with an opaque body.
        // Treat those as layers, not independent depth-writing surfaces.
        // Include skin weights so unrelated surfaces that move differently
        // never qualify merely because they coincide in the resting pose.
        let repaired = 0;
        root.traverse(child => {
            const materials = Array.isArray(child.material) ? child.material : [];
            const geometry = child.geometry;
            const positions = geometry?.attributes?.position;
            const indices = geometry?.index;
            if (!positions || !indices || !materials.some(m => m?.map?.transparent)) return;
            const signature = offset => {
                const points = [];
                for (let j = 0; j < 3; j++) {
                    const i = indices.getX(offset + j);
                    const values = [positions.getX(i), positions.getY(i), positions.getZ(i)];
                    for (const name of ['skinIndex', 'skinWeight']) {
                        const a = geometry.attributes[name];
                        if (a) values.push(a.getX(i), a.getY(i), a.getZ(i), a.getW(i));
                    }
                    points.push(values.map(v => v.toFixed(5)).join(','));
                }
                // Cyclic rotations preserve winding; reversed faces are not decals.
                return [points.join('|'), [points[1], points[2], points[0]].join('|'),
                    [points[2], points[0], points[1]].join('|')].sort()[0];
            };
            const baseTriangles = new Set();
            for (const group of geometry.groups || []) {
                const material = materials[group.materialIndex];
                if (!material?.isMMDToonMaterial || material.opacity < .999 || material.map?.transparent) continue;
                for (let i = group.start; i < group.start + group.count; i += 3) baseTriangles.add(signature(i));
            }
            if (!baseTriangles.size) return;
            for (const group of geometry.groups || []) {
                const material = materials[group.materialIndex];
                if (!material?.isMMDToonMaterial || !material.map?.transparent || group.count < 9) continue;
                let matches = 0;
                for (let i = group.start; i < group.start + group.count; i += 3) {
                    if (baseTriangles.has(signature(i))) matches++;
                }
                if (matches / (group.count / 3) < .95) continue;
                material.transparent = true;
                material.depthWrite = false;
                material.polygonOffset = true;
                material.polygonOffsetFactor = -1;
                material.polygonOffsetUnits = -1;
                material.needsUpdate = true;
                repaired++;
            }
        });
        return repaired;
    }

    setEyeTrackingTarget(x, y) {
        this.eyeTrackingTarget = { x: Math.max(-1, Math.min(1, x)), y: Math.max(-1, Math.min(1, y)) };
        this.live2d?.setGazeTarget(this.eyeTrackingTarget.x,this.eyeTrackingTarget.y);
    }

    clearEyeTracking() {
        this._restoreCursorHeadPose();
        this.eyeTrackingTarget = null;
        this.eyeTrackingPosition={x:0,y:0};
        this.headGazePosition={x:0,y:0};
        const lookAt = this.vrm?.lookAt;
        if (lookAt) { lookAt.yaw = 0; lookAt.pitch = 0; }
        this.live2d?.clearGaze();
    }

    _animateEyeTracking(delta) {
        const target = this.eyeTrackingTarget || { x: 0, y: 0 };
        this.eyeTrackingPosition ||= { x: 0, y: 0 };
        this.headGazePosition ||= { x: 0, y: 0 };
        const step = Math.min(delta, 0.1);
        // Cursor response settles in 1–3 frames, without a second slow head filter at
        // glance speed, which is what keeps a 60 Hz cursor feed from looking twitchy.
        const eyeFollow = 1 - Math.exp(-step / 0.006);
        const headFollow = 1 - Math.exp(-step / 0.016);
        for (const axis of ['x', 'y']) {
            this.eyeTrackingPosition[axis] += (target[axis] - this.eyeTrackingPosition[axis]) * eyeFollow;
            this.headGazePosition[axis] += (target[axis] - this.headGazePosition[axis]) * headFollow;
        }
        if (this.vrm?.lookAt) {
            // three-vrm's lookAt applier keeps VRM 0.x and 1.0 axis conventions
            // (and expression-based look-at) out of this file; it takes degrees.
            this.vrm.lookAt.autoUpdate = false;
            this.vrm.lookAt.yaw = this.eyeTrackingPosition.x * 48;
            this.vrm.lookAt.pitch = this.eyeTrackingPosition.y * 36;
        } else {
            for (const key of ['leftEye', 'rightEye']) {
                const entry = this.animationBones[key];
                if (entry) entry.bone.rotation.set(entry.rest.x + this.eyeTrackingPosition.y * 0.20,
                    entry.rest.y + this.eyeTrackingPosition.x * 0.30, entry.rest.z, entry.rest.order);
            }
        }
        // Explicit cursor gaze also adds a head glance during camera tracking.
        // Restore this additive offset before the next animation pass, including
        // VTuber/dance paths that do not rewrite the head every frame.
        const head = this.animationBones.head;
        if (head) {
            this._restoreCursorHeadPose();
            const rotation = head.bone.rotation;
            const base = {x: rotation.x, y: rotation.y, z: rotation.z, order: rotation.order};
            const pitchSign = this.vrm ? -1 : 1;
            rotation.set(base.x + this.headGazePosition.y * 0.15 * pitchSign,
                base.y + this.headGazePosition.x * 0.30, base.z, base.order);
            this._cursorHeadPose = {bone: head.bone, base,
                applied: {x: rotation.x, y: rotation.y, z: rotation.z}};
        }
    }

    _restoreCursorHeadPose() {
        const pose = this._cursorHeadPose;
        this._cursorHeadPose = null;
        if (!pose) return;
        const rotation = pose.bone.rotation;
        // Leave a newer camera/calibration/manual pose intact.
        if (Math.abs(rotation.x-pose.applied.x)<1e-6 && Math.abs(rotation.y-pose.applied.y)<1e-6 &&
            Math.abs(rotation.z-pose.applied.z)<1e-6)
            rotation.set(pose.base.x, pose.base.y, pose.base.z, pose.base.order);
    }

    _shouldUseCursorGaze() {
        return !this.userTracking || this.eyeTrackingEnabled === true;
    }

    setActivity(activity) {
        this.activity = ['idle', 'thinking', 'talking'].includes(activity) ? activity : 'idle';
        if (this.activity !== 'talking') this.speechLevel = 0;
    }

    setUserTracking(enabled, {preserveIntent=false} = {}) {
        if(!preserveIntent)this.userTrackingRequested=!!enabled;
        if(this.live2d){this.userTracking=!!enabled;this.live2d.neutral=null;return;}
        if (this.userTracking && !enabled) this.avatarRetarget?.reset();
        this.userTracking = !!enabled;
        if (enabled) {
            this.avatarRetarget = new AvatarRetarget(this);
            this.avatarRetarget.setMouthTracking(this.trackingMouthEnabled);
            this.userTrackingSample = null;
            this.activity = 'idle';
        }
        this.physics?.reset();
        if (this.physics?.bullet) {
            const bullet = this.physics.bullet;
            this.model.updateMatrixWorld(true);
            bullet.owned(() => bullet.engine.reset());
            for (const rigid of bullet.engine.bodies) {
                rigid.body.setLinearVelocity(bullet.zero);
                rigid.body.setAngularVelocity(bullet.zero);
            }
            bullet.accumulator = 0;
            this.physics._resetBulletJitterGuard?.();
        }
    }

    setVtuberTrackingMode(enabled) {
        this.vtuberTrackingMode = !!enabled;
        // Leaving the companion add-on must not wipe an expression the user or
        // the phone app chose; only leaving pure VTuber tracking resets it.
        if (!enabled && !this.companionTracking) this.clearManualExpression();
        // VTuber uses the library window, which previously kept OrbitControls'
        // default left-rotate mapping instead of the companion's drag mapping.
        this._configureModelControls();
        if (this.vtuberTrackingMode) {
            this._applyTrackingRestPose();
            // In face-tracking mode, only the user's detected eye-blink
            // blendshapes should close the avatar's eyes.
            this.isBlinking = false;
            this.blinkProgress = 0;
            this.blinkTimer = 0;
            this.setMorph('Blink', 0);
        }
    }

    // The Companion camera add-on still needs the VTuber rig preparation
    // (relaxed arms, tracked blink) but must not mute the AI companion itself.
    setCompanionTracking(enabled) {
        this.companionTracking = !!enabled;
    }

    _shouldAutoBlink() {
        return !this.userTracking && !this.vtuberTrackingMode;
    }

    _applyTrackingRestPose() {
        if(!this.model||this.live2d)return;
        const bones=this.animationBones;
        for(const side of ['left','right'])for(const part of ['Arm','Elbow','Wrist']){
            const entry=bones[side+part];if(entry?.rest)entry.bone.rotation.copy(entry.rest);
        }
        this.model.updateMatrixWorld(true);
        const rootRotation=this.model.getWorldQuaternion(new THREE.Quaternion());
        const inverse=new THREE.Matrix4().copy(this.model.matrixWorld).invert();
        for(const side of ['left','right']){
            const arm=bones[side+'Arm'],elbow=bones[side+'Elbow'];if(!arm||!elbow)continue;
            const origin=arm.bone.getWorldPosition(new THREE.Vector3());
            const direction=elbow.bone.getWorldPosition(new THREE.Vector3()).sub(origin).normalize();
            if(direction.lengthSq()<1e-8)continue;
            const sign=Math.sign(origin.clone().applyMatrix4(inverse).x)||(side==='left'?1:-1);
            const lowered=new THREE.Vector3(sign*.18,-1,.06).normalize().applyQuaternion(rootRotation);
            const correction=new THREE.Quaternion().setFromUnitVectors(direction,lowered);
            const world=arm.bone.getWorldQuaternion(new THREE.Quaternion());
            const parent=arm.bone.parent.getWorldQuaternion(new THREE.Quaternion()).invert();
            arm.bone.quaternion.copy(parent.multiply(correction.multiply(world)));
            arm.trackingRest=arm.bone.rotation.clone();
            for(const part of ['Elbow','Wrist']){
                const entry=bones[side+part];if(!entry)continue;
                entry.bone.rotation.x+=part==='Elbow'?.1:.04;
                entry.trackingRest=entry.bone.rotation.clone();
            }
            this.model.updateMatrixWorld(true);
        }
    }

    updateUserTracking(sample) { this.userTrackingSample = {...sample, receivedAt: performance.now()}; }

    setCollaboratorPose(pose) { this.collaboratorPose = pose && typeof pose === 'object' ? pose : null; }

    _applyCollaboratorPose() {
        const pose=this.collaboratorPose;
        if(!pose)return;
        if(this.live2d&&pose.parameters){
            const core=this.live2d.avatar?.internalModel?.coreModel;
            if(core)for(const [id,value]of Object.entries(pose.parameters))if(Number.isFinite(value)&&core.getParameterIndex(id)>=0)core.setParameterValueById(id,value);
            return;
        }
        if(!this.model||pose.kind!=='3d')return;
        let boneIndex=0,meshIndex=0;
        this.model.traverse(node=>{
            if(node.isBone){const data=pose.bones?.[boneIndex++];if(data){if(data.q?.length===4)node.quaternion.fromArray(data.q);if(data.p?.length===3)node.position.fromArray(data.p);}}
            if(node.isMesh&&node.morphTargetInfluences){const values=pose.morphs?.[meshIndex++];if(values)for(let i=0;i<Math.min(values.length,node.morphTargetInfluences.length);i++)if(Number.isFinite(values[i]))node.morphTargetInfluences[i]=values[i];}
        });
    }
    setTrackingMouthEnabled(enabled) {
        this.trackingMouthEnabled = Boolean(enabled);
        this.avatarRetarget?.setMouthTracking(this.trackingMouthEnabled);
        if (this.live2d && !this.trackingMouthEnabled) {
            for (const name of ['A','I','U','E','O']) this.live2d.setMorph(name, 0);
        }
    }
    calibrateUserTracking() { if(this.live2d)this.live2d.calibrate();else this.avatarRetarget?.calibrate(this.userTrackingSample); }

    setSpeechLevel(level) {
        this.speechLevel = Math.max(0, Math.min(1, level));
    }

    setPhysicsMode(mode) {
        const applied = this.physics.setMode(mode);
        this._syncVrmPhysics();
        return applied;
    }

    /**
     * Exclude duplicate-named / degenerate physics chains (the classic
     * ported-PMX glitch source) from the simulation. Re-runs physics
     * attachment only — the model, textures and shaders stay untouched.
     */
    setGlitchFix(enabled) {
        this.physics.glitchFixPolicy = enabled ? 'on' : 'off';
        this.physics.glitchFixEnabled = !!enabled;
        if (!this.model || this.vrm) return this.physicsInfo;
        const reserved = new Set(Object.values(this.animationBones).map(e => e.bone.name));
        try {
            this.physicsInfo = this.physics.attach(this.model, reserved);
        } catch (error) {
            console.warn('Physics re-attachment failed:', error);
        }
        return this.physicsInfo;
    }

    repairPhysics() {
        if (!this.model || this.vrm) return null;
        this.physics.forceSpring = true;
        this.physics.forceSpringReason = 'Physics reset: safe spring-chain simulation is active.';
        return this.setGlitchFix(true);
    }

    setPhysicsStrength(value) {
        const applied = this.physics.setStrength(value);
        this._syncVrmPhysics();
        return applied;
    }

    setWindStrength(value) {
        const applied = this.physics.setWindStrength(value);
        this._syncVrmPhysics();
        return applied;
    }

    /**
     * Map the physics mode onto the VRM runtime's own spring bones by
     * scaling their per-joint settings, so Off/Subtle/Normal/Lively behave
     * the same for VRM avatars as for PMX rigs.
     */
    _syncVrmPhysics() {
        const jointList = this.vrm?.springBoneManager?.joints;
        if (!jointList || typeof jointList[Symbol.iterator] !== 'function') return;
        const factors = { off: 0, subtle: 0.55, normal: 1, lively: 1.45 };
        const factor = this.physics.mode === 'custom' ? this.physics.strength : factors[this.physics.mode] ?? 1;
        this._vrmJointRest ||= new WeakMap();
        for (const joint of jointList) {
            const settings = joint?.settings;
            if (!settings) continue;
            let rest = this._vrmJointRest.get(joint);
            if (!rest) {
                rest = { stiffness: settings.stiffness, gravityPower: settings.gravityPower, dragForce: settings.dragForce,
                    gravityDir: settings.gravityDir?.clone?.() };
                this._vrmJointRest.set(joint, rest);
            }
            if (factor === 0 || this.physics.disabledBones?.has(joint.bone) || this.diagnosticFrozenBones?.has(joint.bone)) {
                // "Off" parks every strand at its rest pose: no forces, and
                // full drag kills the verlet inertia within a step.
                settings.stiffness = 0;
                settings.gravityPower = 0;
                settings.dragForce = 1;
            } else {
                settings.stiffness = rest.stiffness * factor;
                settings.gravityPower = rest.gravityPower * factor;
                settings.dragForce = factor === 1 ? rest.dragForce : Math.min(1, Math.max(0, rest.dragForce / factor));
            }
            if (!this.physics.disabledBones?.has(joint.bone) && !this.diagnosticFrozenBones?.has(joint.bone) && rest.gravityDir && settings.gravityDir) {
                settings.gravityDir.copy(rest.gravityDir);
                const wind = (this.physics.windStrength || 0) * .15 * factor;
                if (wind > 0) {
                    const base = rest.gravityPower * factor;
                    const x=rest.gravityDir.x*base+wind,y=rest.gravityDir.y*base,z=rest.gravityDir.z*base;
                    const length=Math.hypot(x,y,z);
                    settings.gravityPower=length;
                    if(length>0) settings.gravityDir.set(x/length,y/length,z/length);
                }
            }
        }
        // Zero forces alone preserve an already displaced tail. Reset the
        // runtime's particles and bone rotations when switching physics off.
        if (factor === 0) this.vrm.springBoneManager.reset?.();
    }

    setEmotionFromText(text) {
        // Only restrained brow expressions; mouth vowels remain under lip-sync.
        this.emotion = /\b(sorry|sad|hurt|worried|difficult|upset)\b/i.test(text) ? 'concerned'
            : /\b(wow|yay|awesome|congratulations|excited)\b/i.test(text) ? 'happy' : 'friendly';
        this.gestureStyle = classifySpeechGesture(text);
    }

    _avoidArmClipping() {
        if (!this.model || this.userTracking) return;
        if (!this.armClearance || this.armClearance.root !== this.model) this.armClearance = new ArmClearance(this);
        this.armClearance.update();
    }

    applyHairScreenDrag(dx, dy) {
        if (!this.model || !Number.isFinite(dx) || !Number.isFinite(dy)) return;
        // Convert screen displacement into the unscaled MMD solver space.
        const height = Math.max(1,this.renderer.domElement.clientHeight);
        const distance = this.camera.position.distanceTo(this.controls.target);
        const units = 2*distance*Math.tan(this.camera.fov*Math.PI/360)/height;
        this.camera.updateMatrixWorld();
        const movement = this._hairDragVector.setFromMatrixColumn(this.camera.matrixWorld,0).multiplyScalar(dx*units);
        movement.addScaledVector(this._hairDragAxis.setFromMatrixColumn(this.camera.matrixWorld,1),-dy*units);
        if (this.physics.bullet) {
            this.model.getWorldQuaternion(this._hairDragRotation ??= new THREE.Quaternion());
            movement.applyQuaternion(this._hairDragRotation.invert());
            movement.divideScalar(Math.max(.001,this.model.getWorldScale(this._hairDragAxis).x));
        }
        this.physics.applyCharacterDrag(movement);
    }

    _animateCharacter(delta, elapsed) {
        if (!this.model) return;
        if(this.dance?.update(delta))return;
        if (this.userTracking) {
            if(this.physics)this.physics.allowIdleSleep = false;
            try { this.avatarRetarget.apply(this.userTrackingSample, delta); }
            catch(error) {
                // A bad tracking packet must not enter the fatal GPU/render
                // cleanup path and dispose an otherwise healthy avatar.
                this.userTracking=false;this.userTrackingSample=null;
                try { this.avatarRetarget?.reset(); } catch(_) {}
                console.error('Tracking paused; model preserved:',error);
                window.dispatchEvent(new CustomEvent('sakura-tracking-error',{detail:String(error.message||error)}));
                return;
            }
            // Keep a little authored life under the tracked pose; retarget
            // rewrites these bones every frame, so the offset never accumulates.
            if (this.companionTracking) {
                const sway = Math.sin(elapsed * .43) * .03 + Math.sin(elapsed * .23 + 1.4) * .008;
                for (const key of ['torso', 'chest']) {
                    const entry = this.animationBones?.[key];
                    if (entry?.bone) entry.bone.rotation.z += sway * (key === 'torso' ? 1 : .4);
                }
            }
            return;
        }
        if (this.vtuberTrackingMode && (this.chatReaderActive || this.chatReaderMotion)) {
            applyChatReaderLean(this, delta);
            return;
        }
        // VTuber playback animates lips only. It must never activate the AI
        // companion's idle lean, conversational hands or thinking gestures.
        if(this.vtuberTrackingMode){
            // Physics/recalibration can restore the authored A/T bind pose after
            // loading. Keep untracked VTuber arms at the computed relaxed pose.
            if(!this.userTracking)for(const side of ['left','right'])for(const part of ['Arm','Elbow','Wrist']){
                const entry=this.animationBones[side+part];
                if(entry?.trackingRest)entry.bone.rotation.copy(entry.trackingRest);
            }
            return;
        }
        const alpha = 1 - Math.exp(-Math.min(delta, 0.1) / 0.22);
        this.talkBlend += ((this.activity === 'talking' ? 1 : 0) - this.talkBlend) * alpha;
        this.thinkBlend += ((this.activity === 'thinking' ? 1 : 0) - this.thinkBlend) * alpha;
        // A gesture has preparation, a stroke and a settling phase. Alternate
        // hands with occasional quiet beats instead of continuously waving both.
        this.conversationMotion ||= { time: 0, beat: 0, duration: 1.8, energy: 0 };
        const motion = this.conversationMotion;
        const dt = Math.max(0, Math.min(delta, 0.1));
        const talkingNow = this.activity === 'talking';
        if (motion.wasTalking && !talkingNow && !this.vtuberTrackingMode) {
            motion.settleTime = 0;
            motion.settleSide = -(motion.settleSide || 1);
            motion.settling = true;
        }
        motion.wasTalking = talkingNow;
        if (motion.settling) {
            motion.settleTime += dt;
            if (motion.settleTime >= 6 || talkingNow || this.vtuberTrackingMode) motion.settling = false;
        }
        // A slow weight shift followed by a relaxed return, rather than an
        // abrupt neutral pose as soon as the final audio chunk ends.
        const settlePhase = motion.settling ? motion.settleTime / 6 : 0;
        const settleLean = motion.settling
            ? motion.settleSide * Math.pow(Math.sin(Math.PI * settlePhase), 2) * .045 : 0;
        motion.energy += ((this.speechLevel || 0) - motion.energy) * (1 - Math.exp(-dt / .32));
        if (this.activity === 'talking') motion.time += dt;
        if (motion.time >= motion.duration) {
            motion.time -= motion.duration;
            motion.beat++;
            motion.duration = 1.55 + ((motion.beat * 7) % 5) * .20;
        }
        const phase = motion.time / motion.duration;
        const speech = this.talkBlend * (0.4 + motion.energy * 0.6);
        // Unboosted, wind-free idle should settle instead of continuously
        // exciting hair and clothing with scripted torso/head oscillations.
        const calmIdle = (this.physicsBoost ?? 0) === 0 && !this.physics?.windStrength
            && this.activity === 'idle' && this.talkBlend < .01 && this.thinkBlend < .01 && !motion.settling;
        const idleScale = calmIdle ? 0 : 1;
        if(this.physics)this.physics.allowIdleSleep = calmIdle;
        const breathe = Math.sin(elapsed * 1.6) * idleScale;
        const gesture = Math.sin(elapsed * .36) * .45 * idleScale;
        // Keep the AI companion's weight gently shifting after speech ends.
        // The layered slow waves avoid a visible loop or the old six-second
        // settle-then-freeze behavior; webcam VTuber tracking stays untouched.
        const companionSway = this.vtuberTrackingMode || this.isShenheQipaoModel ? 0
            : Math.sin(elapsed * .43) * .034 + Math.sin(elapsed * .23 + 1.4) * .008;
        const motif = motion.beat % 7;
        const phrase=speechGestureWeights(this.gestureStyle,phase,motif);
        const leftGesture = speech * phrase.left;
        const rightGesture = speech * phrase.right;
        const emphasis = phrase.stroke * speech * (this.emotion === 'happy' ? 1.15 : this.emotion === 'concerned' ? .65 : 1);
        const handTurn = this.gestureStyle === 'question' ? .23 : this.gestureStyle === 'explain' ? .15
            : this.gestureStyle === 'celebrate' ? .18 : this.gestureStyle === 'reassure' ? .10 : .08;
        const rotate = (key, x, y, z) => {
            const entry = this.animationBones[key];
            if (!entry) return;
            // Use the arm direction calculated from this model's actual bind
            // geometry. A fixed 0.72-radian offset leaves T-rest rigs in A-pose.
            if(entry.trackingRest && /^(left|right)Arm$/.test(key)) {
                const legacy=this.vrm?(key==='leftArm'?1.35:-1.35):(key==='leftArm'?-.72:.72);
                x+=entry.trackingRest.x-entry.rest.x;
                y+=entry.trackingRest.y-entry.rest.y;
                z+=entry.trackingRest.z-entry.rest.z-legacy;
            }
            entry.motion ||= {x, y, z};
            const follow = 1 - Math.exp(-dt / (key.includes('Wrist') ? .19 : .13));
            for (const [axis, value] of Object.entries({x, y, z})) entry.motion[axis] += (value - entry.motion[axis]) * follow;
            entry.bone.rotation.set(entry.rest.x + entry.motion.x, entry.rest.y + entry.motion.y, entry.rest.z + entry.motion.z, entry.rest.order);
        };
        rotate('torso', breathe * 0.012, gesture * 0.022, companionSway + settleLean);
        rotate('chest', breathe * 0.018, (leftGesture - rightGesture) * 0.045, -gesture * 0.015 - companionSway * .24 - settleLean * .3);
        rotate('neck', -emphasis * .008, 0, -gesture * 0.012 - companionSway * .22);
        rotate('head', -emphasis * .025 + this.thinkBlend * .015,
            Math.sin(elapsed * 0.43) * 0.045 * idleScale + (leftGesture - rightGesture) * 0.035,
            this.thinkBlend * 0.085 + gesture * 0.028 - companionSway * .18 - settleLean * .4);
        // Lower the arms out of the model's bind A-pose and soften the elbows.
        // Talking alternates inviting, open-hand gestures from that resting pose.
        rotate('leftArm', leftGesture * .28, -.10 - leftGesture * .24,
            (this.vrm ? 1.35 - leftGesture * .80 : -.72 + leftGesture * .80) + breathe * .008);
        rotate('rightArm', rightGesture * .28, .10 + rightGesture * .24,
            (this.vrm ? -1.35 + rightGesture * .80 : .72 - rightGesture * .80) - breathe * .008);
        rotate('leftElbow', leftGesture * .04, -.18 - leftGesture * 1.05, -.045);
        rotate('rightElbow', rightGesture * .04, .18 + rightGesture * 1.05, .045);
        rotate('leftWrist', leftGesture * .08, leftGesture * handTurn, -.045 + leftGesture * .16);
        rotate('rightWrist', rightGesture * .08, -rightGesture * handTurn, .045 - rightGesture * .16);
        for (const finger of this.conversationFingers || []) {
            const openness = finger.side === 'left' ? leftGesture : rightGesture;
            const target = (finger.finger === 0 ? .06 : .16 + finger.finger * .025) * (1 - openness * .85);
            finger.curl += (target - finger.curl) * (1 - Math.exp(-dt / .2));
            finger.bone.rotation.set(finger.rest.x, finger.rest.y,
                finger.rest.z + finger.curl * (finger.side === 'left' ? -1 : 1), finger.rest.order);
        }
        this._avoidArmClipping?.();
        const targets = {
            // PMX smile morphs can also stretch the mouth. Fade them while
            // speaking so they don't fight the audio-driven opening morph.
            smile: (this.emotion === 'happy' ? 0.3 : this.emotion === 'friendly' ? 0.1 : 0) * (1 - this.talkBlend),
            concern: this.emotion === 'concerned' ? 0.22 : 0,
            focus: this.thinkBlend * 0.18,
        };
        if(this.areAiExpressionsAutomatic?.()===false)for(const key of Object.keys(targets))targets[key]=0;
        for (const [key, name] of Object.entries(this.expressionMorphs || {})) {
            this.expressionWeights[key] += (targets[key] - this.expressionWeights[key]) * alpha;
            if (name) this.setMorph(name, this.expressionWeights[key]);
        }
    }

    _visibleModelBounds(object) {
        const box = new THREE.Box3();
        const point = new THREE.Vector3();
        object.updateMatrixWorld(true);
        object.traverse(mesh => {
            const geometry = mesh.geometry;
            if (!geometry?.attributes?.position || mesh.visible === false) return;
            const materials = Array.isArray(mesh.material) ? mesh.material : [mesh.material];
            const groups = geometry.groups.length ? geometry.groups : [{
                start: 0, count: geometry.index?.count || geometry.attributes.position.count, materialIndex: 0
            }];
            for (const group of groups) {
                const material = Array.isArray(mesh.material) ? materials[group.materialIndex] : mesh.material;
                if (!material || material.visible === false || material.opacity <= 0.001) continue;
                const step = Math.max(1, Math.floor(group.count / 512));
                for (let i = group.start; i < group.start + group.count; i += step) {
                    const index = geometry.index ? geometry.index.getX(i) : i;
                    mesh.getVertexPosition(index, point);
                    point.applyMatrix4(mesh.matrixWorld);
                    if ([point.x, point.y, point.z].every(Number.isFinite)) box.expandByPoint(point);
                }
            }
        });
        return box.isEmpty() ? new THREE.Box3().setFromObject(object) : box;
    }

    _autoFrame(object) {
        if(this.live2d){this.live2d.pan={x:0,y:0};this.live2d.fit();return;}
        object.updateMatrixWorld(true);
        // Hidden morph variants and helper surfaces are not visible characters
        // and must not drag the camera thousands of units away.
        const box = this._visibleModelBounds(object);
        const center = box.getCenter(new THREE.Vector3());
        const size = box.getSize(new THREE.Vector3());
        window.pywebview?.api.model_frame_status([center.x, center.y, center.z], [size.x, size.y, size.z]);

        const headBone = this.vrm?.humanoid?.getRawBoneNode?.('head')
            || this.vrm?.humanoid?.getNormalizedBoneNode?.('head')
            || this.animationBones.head?.bone;
        if (this.fullModelView || this.desktopMode || !headBone) {
            const verticalFov = THREE.MathUtils.degToRad(this.camera.fov);
            const distance = Math.max(
                size.y / (2 * Math.tan(verticalFov / 2)),
                size.x / (2 * Math.tan(verticalFov / 2) * this.camera.aspect)
            ) * (this.desktopMode ? 1.25 : 1.55);
            this.controls.target.copy(center);
            this.camera.position.set(center.x, center.y, center.z + distance + size.z / 2);
            this.camera.far = Math.max(1000, distance * 4 + size.length());
            this.camera.updateProjectionMatrix();
            this.controls.update();
            return;
        }

        if (this.vrm) {
            // VRM uses different model scales from PMX. Frame its upper body
            // from world bounds rather than the PMX camera's fixed distances.
            const head = headBone.getWorldPosition(new THREE.Vector3());
            const framingHeight = size.y * .6;
            const targetY = Math.min(box.max.y - framingHeight / 2,
                Math.max(box.min.y + framingHeight / 2, head.y - size.y * .18));
            this.controls.target.set(head.x, targetY, head.z);
            const verticalFov = THREE.MathUtils.degToRad(this.camera.fov);
            const distance = Math.max(
                framingHeight / (2 * Math.tan(verticalFov / 2)),
                size.x * .55 / (2 * Math.tan(verticalFov / 2) * this.camera.aspect)
            ) * 1.15 + size.z / 2;
            this.camera.position.set(head.x, targetY, head.z + distance);
            this.camera.far = Math.max(1000, distance * 4 + size.length());
            this.camera.updateProjectionMatrix();
            this.camera.lookAt(this.controls.target);
            this.controls.update();
            return;
        }

        // Target upper 75% of height (the face/chest region)
        const head = this.animationBones.head.bone.getWorldPosition(new THREE.Vector3());
        const origin = object.getWorldPosition(new THREE.Vector3());
        const headHeight = Math.abs(head.y - origin.y);
        const framingHeight = headHeight > 0.1 && size.y > headHeight * 3
            ? headHeight * 1.3 : size.y;
        const faceHeight = head.y - framingHeight * 0.05;
        this.controls.target.set(head.x, faceHeight, head.z);

        // Position camera nicely in front of face
        const dist = Math.max(framingHeight * 0.5, 6);
        this.camera.position.set(head.x, faceHeight + 0.5, head.z + dist);
        this.camera.far = Math.max(1000, dist * 4 + size.length());
        this.camera.updateProjectionMatrix();
        this.camera.lookAt(this.controls.target);
        this.controls.update();
    }

    captureSpoutFrame(maxSize=720) {
        if(this.live2d){if(maxSize===0)maxSize=Math.min(2560,Math.max(this.live2d.app.view.width,this.live2d.app.view.height));return this.live2d.capture(maxSize);}
        if (!this.model || this._displayLoading) return null;
        const aspect=this.camera.aspect;
        // Spout's native option follows the actual drawing buffer, including
        // display pixel ratio, rather than enlarging a 720px preview in OBS.
        if(maxSize===0){const buffer=this.renderer.getDrawingBufferSize(new THREE.Vector2());maxSize=Math.min(2560,Math.max(buffer.x,buffer.y));}
        const width=Math.max(1,Math.round(aspect>=1?maxSize:maxSize*aspect));
        const height=Math.max(1,Math.round(aspect>=1?maxSize/aspect:maxSize));
        if (!this._spoutTarget || this._spoutTarget.width!==width || this._spoutTarget.height!==height) {
            this._spoutTarget?.dispose();
            this._spoutTarget=new THREE.WebGLRenderTarget(width,height,{samples:Math.min(4,this.renderer.capabilities.maxSamples||0)});
            this._spoutTarget.texture.colorSpace=THREE.SRGBColorSpace;
            this._spoutPixels=new Uint8Array(width*height*4);
        }
        const previous=this.renderer.getRenderTarget(),background=this.scene.background;
        const viewport=this.renderer.getViewport(new THREE.Vector4()),scissor=this.renderer.getScissor(new THREE.Vector4()),scissorTest=this.renderer.getScissorTest();
        const color=this.renderer.getClearColor(new THREE.Color()),alpha=this.renderer.getClearAlpha();
        try {
            this.scene.background=null;this.renderer.setClearColor(0,0);
            this.renderer.setRenderTarget(this._spoutTarget);
            this.renderer.setViewport(0,0,width,height);this.renderer.setScissorTest(false);
            this.renderer.clear();
            this.renderer.render(this.scene,this.camera);
            this.renderer.readRenderTargetPixels(this._spoutTarget,0,0,width,height,this._spoutPixels);
            // WebGL starts at the bottom; send top-down, straight-alpha RGBA.
            const pixels=new Uint8Array(this._spoutPixels.length),stride=width*4;
            for(let y=0;y<height;y++)pixels.set(this._spoutPixels.subarray((height-1-y)*stride,(height-y)*stride),y*stride);
            return {pixels,width,height};
        } finally {
            this.renderer.setRenderTarget(previous);this.renderer.setClearColor(color,alpha);this.scene.background=background;
            this.renderer.setViewport(viewport);this.renderer.setScissor(scissor);this.renderer.setScissorTest(scissorTest);
        }
    }

    releaseSpoutFrame() {
        this._spoutTarget?.dispose();this._spoutTarget=null;this._spoutPixels=null;
    }

    captureAvatar() {
        if(this.live2d)return this.live2d.capture(768).canvas.toDataURL('image/jpeg',.85).split(',')[1];
        if (!this.model) return null;
        const frame=this.captureSpoutFrame(768);
        if(!frame)return null;
        // Never repaint the on-screen WebGL canvas from a preview timer.
        // Qt's transparent compositor can expose mixed/stale damage tiles
        // through settings while that extra frame is being presented.
        const source=document.createElement('canvas');source.width=frame.width;source.height=frame.height;
        source.getContext('2d').putImageData(new ImageData(new Uint8ClampedArray(frame.pixels),frame.width,frame.height),0,0);
        const output = document.createElement('canvas');
        output.width = frame.width;
        output.height = frame.height;
        const context = output.getContext('2d');
        context.fillStyle = '#202830'; context.fillRect(0, 0, output.width, output.height);
        context.drawImage(source, 0, 0, output.width, output.height);
        return output.toDataURL('image/jpeg', .85).split(',')[1];
    }

    clearManualExpression() {
        for(const name of this.manualExpressions?.keys()||[])if(!this.live2d){for(const p of this.customExpressions?.[name]?.parameters||[])this.setMorph(p.id,0);this.setMorph(name,0);}
        this.manualExpressions?.clear();
        this.live2d?.clearExpression();
        if (this.manualExpression) {
            if (this.live2d) this.live2d.clearExpression();
            else this.setMorph(this.manualExpression.name, 0);
        }
        this.manualExpression = null;
    }

    setMorph(name, value) {
        if(this.live2d){this.live2d.setMorph(name,value);return;}
        if (this.vrm?.expressionManager) {
            this.vrm.expressionManager.setValue(this.resolvedVowels[name] || name, value);
            return;
        }
        // Direct match
        if (this.morphMap[name]) {
            for (const item of this.morphMap[name]) {
                item.mesh.morphTargetInfluences[item.index] = value;
            }
            return;
        }

        // Try resolved vowels (A, I, U, E, O)
        const resolved = this.resolvedVowels ? this.resolvedVowels[name] : null;
        if (resolved && this.morphMap[resolved]) {
            for (const item of this.morphMap[resolved]) {
                item.mesh.morphTargetInfluences[item.index] = value;
            }
        }
    }

    setVowelWeights(weights) {
        if(this.mouthOptions?.source==='off'&&!this.audioPlaybackActive)weights={A:0,I:0,U:0,E:0,O:0};
        const mappedWeights={};
        // weights: { A: float, I: float, U: float, E: float, O: float }
        for (const [vowel, val] of Object.entries(weights)) {
            const mapped=this.mouthOptions?.mapping?.[vowel];
            if(mapped==='none')continue;
            const name=mapped||vowel;mappedWeights[name]=Math.max(mappedWeights[name]||0,THREE.MathUtils.clamp(val,0,1));
        }
        for(const [name,value]of Object.entries(mappedWeights))this.setMorph(name,value);
    }

    resetMouth() {
        for(const name of Object.values(this.mouthOptions?.mapping||{}))if(name&&name!=='none')this.setMorph(name,0);
        ['A', 'I', 'U', 'E', 'O'].forEach((v) => this.setMorph(v, 0));
    }

    getMorphNames() {
        return this.allMorphNames;
    }

    _initBloom() {
        if (this.bloomPass) return;
        this.bloomBase = new THREE.WebGLRenderTarget(1, 1, { type: THREE.HalfFloatType });
        // PMX clothing often has almost coplanar front/back surfaces. The
        // default offscreen depth buffer can lose precision versus the canvas.
        this.bloomBase.depthTexture = new THREE.DepthTexture(1, 1, THREE.FloatType);
        this.bloomBase.samples = Math.min(4, this.renderer.capabilities.maxSamples || 0);
        this.bloomWork = new THREE.WebGLRenderTarget(1, 1, { type: THREE.HalfFloatType, depthBuffer: false });
        this.bloomPass = new UnrealBloomPass(new THREE.Vector2(1, 1), 1, 0.6, 0.8);
        this.bloomCopy = new FullScreenQuad(new THREE.ShaderMaterial({
            uniforms: { image: { value: null } },
            vertexShader: 'varying vec2 uvOut; void main(){uvOut=uv;gl_Position=vec4(position.xy,0.,1.);}',
            fragmentShader: 'uniform sampler2D image; varying vec2 uvOut; void main(){gl_FragColor=texture2D(image,uvOut);}',
            depthTest: false, depthWrite: false
        }));
        this.bloomFinal = new FullScreenQuad(new THREE.ShaderMaterial({
            uniforms: { glow: { value: this.bloomPass.renderTargetsHorizontal[0].texture } },
            vertexShader: 'varying vec2 uvOut; void main(){uvOut=uv;gl_Position=vec4(position.xy,0.,1.);}',
            fragmentShader: `uniform sampler2D glow; varying vec2 uvOut;
                void main(){vec3 g=texture2D(glow,uvOut).rgb;
                float halo=clamp(max(g.r,max(g.g,g.b)),0.,1.);
                gl_FragColor=vec4(g,halo);
                #include <tonemapping_fragment>
                #include <colorspace_fragment>
                }`,
            transparent: true, blending: THREE.CustomBlending,
            blendSrc: THREE.OneFactor, blendDst: THREE.OneFactor,
            blendSrcAlpha: THREE.OneMinusDstAlphaFactor, blendDstAlpha: THREE.OneFactor,
            depthTest: false, depthWrite: false
        }));
        this._resizeBloom();
    }

    _resizeBloom() {
        if (!this.bloomPass) return;
        const ratio = Math.min(this.renderer.getPixelRatio(), 1.5);
        const width = Math.max(1, Math.round(window.innerWidth * ratio));
        const height = Math.max(1, Math.round(window.innerHeight * ratio));
        this.bloomBase.setSize(width, height);
        this.bloomWork.setSize(width, height);
        this.bloomPass.setSize(width, height);
    }

    setLightAngles(angle, elevation) {
        const center = this.keyLight.target.position;
        const yaw = THREE.MathUtils.degToRad(Number(angle) || 0);
        const pitch = THREE.MathUtils.degToRad(Math.max(-10, Math.min(90, Number(elevation) || 0)));
        center.set(0, 12, 0);
        this.keyLight.position.set(center.x + Math.sin(yaw)*Math.cos(pitch)*25,
            center.y + Math.sin(pitch)*25, center.z + Math.cos(yaw)*Math.cos(pitch)*25);
    }

    setGlossBoost(value, root=this.model, selectedMaterial=null) {
        const boost = Math.max(0, Math.min(1, Number(value) || 0));
        this.glossBoostValue=boost;
        this.glossOriginals ||= new WeakMap();
        root?.traverse(child => {
            for (const mat of (Array.isArray(child.material) ? child.material : [child.material])) {
                if (!mat) continue;
                const materialBoost=selectedMaterial&&mat!==selectedMaterial?0:boost;
                if(mat.isMToonMaterial&&!mat.isOutline){
                    mat.userData ||= {};
                    if(!mat.userData.sakuraGloss){
                        const uniform={value:materialBoost},compile=mat.onBeforeCompile,key=mat.customProgramCacheKey;
                        mat.userData.sakuraGloss=uniform;
                        mat.onBeforeCompile=function(shader,renderer){
                            compile?.call(this,shader,renderer);
                            shader.uniforms.sakuraGloss=uniform;
                            shader.fragmentShader='uniform float sakuraGloss;\n'+shader.fragmentShader.replace(
                                'vec3 col = reflectedLight.directDiffuse + reflectedLight.indirectDiffuse;',
                                `vec3 col = reflectedLight.directDiffuse + reflectedLight.indirectDiffuse;
                                vec3 sakuraHalf = normalize(normalize(vViewPosition) + normalize(vec3(0.4, 0.7, 1.0)));
                                col += vec3(0.3) * sakuraGloss * pow(max(dot(normal, sakuraHalf), 0.0), 64.0);`);
                        };
                        mat.customProgramCacheKey=function(){return key.call(this)+'|sakura-gloss-v1';};
                        mat.needsUpdate=true;
                    }
                    mat.userData.sakuraGloss.value=materialBoost;
                }
                if (!this.glossOriginals.has(mat)) this.glossOriginals.set(mat, {
                    shininess: mat.shininess, specular: mat.specular?.clone(), roughness: mat.roughness });
                const original = this.glossOriginals.get(mat);
                if (typeof original.shininess === 'number') mat.shininess = THREE.MathUtils.lerp(original.shininess, Math.max(original.shininess, 120), materialBoost);
                if (original.specular) mat.specular.copy(original.specular).lerp(new THREE.Color(0xaaaaaa), materialBoost);
                if (typeof original.roughness === 'number') mat.roughness = THREE.MathUtils.lerp(original.roughness, 0.08, materialBoost);
            }
        });
    }

    setCharacterLightingTarget(material=null) {
        this.characterLightingTarget=material||null;
        this._bloomTargetObjects=[];
        this._bloomLights=[];
        if(material)this.scene?.traverse(object=>{
            if(object.isLight)this._bloomLights.push(object);
            else if(object.isMesh&&(Array.isArray(object.material)?object.material:[object.material]).includes(material))this._bloomTargetObjects.push(object);
        });
        this.setGlossBoost(this.glossBoostValue??Number(localStorage.getItem('sakura_gloss_boost')||0),this.vrm?.scene||this.model,material);
        if(this.controls)this._renderFrame();
    }

    setCharacterGlow(value) {
        this.characterGlow = Math.max(0, Math.min(1, Number(value) || 0));
        if (this.characterGlow > 0) {
            this._initBloom();
            this.bloomPass.strength = this.characterGlow * 1.8;
        }
    }

    setEnvironmentColor(hex, intensity = 1.0) {
        this.envColor = hex;
        this.envIntensity = intensity;
        const color = new THREE.Color(hex);
        if (this.rimLight) {
            this.rimLight.color.copy(color);
            this.rimLight.intensity = 0.9 * intensity;
        }
        if (this.groundLight) {
            this.groundLight.color.copy(color);
            this.groundLight.intensity = 0.4 * intensity;
        }
        if (this.placeholderMesh && this.placeholderMesh.material) {
            this.placeholderMesh.material.color.copy(color);
            this.placeholderMesh.material.emissive.copy(color);
        }
        if (this.innerOrb && this.innerOrb.material) {
            this.innerOrb.material.color.copy(color);
        }
        this.setCharacterGlow(this.characterGlow || 0);
    }

    setRgbBreathing(enabled, onColorChange = null) {
        this.rgbBreathing = !!enabled;
        if (onColorChange) this.onColorChange = onColorChange;
        if (!enabled && this.envColor) {
            this.setEnvironmentColor(this.envColor, this.envIntensity);
        }
    }

    animate() {
        if(this.destroyed)return;
        this.animationFrame=requestAnimationFrame(this.animate);
        if(window.sakuraNativeHidden){this.clock?.getDelta();return;}
        try {
            this._renderFrame();
        } catch (error) {
            // A failed allocation must not be retried on every animation frame.
            const failed = this.model;
            this.model = null;
            this.vrm = null;
            this.animationBones = {};
            this.morphMap = {};
            this.morphMeshes = [];
            this.resolvedVowels = {};
            this.physicsInfo = null;
            this.physics.detach();
            if (failed) {
                try { this._disposeObject(failed); } catch (_) {}
                console.error('Model rendering stopped:', error);
                window.dispatchEvent(new CustomEvent('sakura-model-render-error', {detail: String(error.message || error)}));
            }
        }
    }

    _prepareCompanionSurface() {
        if (this.companionSurface) {
            // Always present a complete default framebuffer after native size
            // changes or offscreen captures, never reuse damaged alpha tiles.
            // Only _releasePresentedFrame may uncover a held frame. Removing
            // it here exposes the cleared drawing buffer before the new draw.
            const size = this.renderer.getSize(this._presentSize ||= new THREE.Vector2());
            this.renderer.setRenderTarget(null);
            this.renderer.setViewport(0, 0, size.x, size.y);
            this.renderer.setScissorTest(false);
            this.renderer.autoClear = true;
            // render() clears and draws in the same submission. A separate
            // clear before animation/physics exposes an empty alpha frame to
            // the native compositor and can flash during expensive updates.
        }

    }

    _renderFrame() {
        // Keep the last image while the old GPU resources are released and
        // the replacement textures/shaders load. No empty scene flashes.
        if (this._displayLoading) { this.clock.getDelta(); return; }
        // CPU speech preparation/model uploads can stall a frame. Advancing
        // VRM spring bones by that entire pause can fling vertices for one
        // frame. Bound simulation steps consistently for all model formats.
        const rawDelta = this.clock.getDelta();
        const delta = Number.isFinite(rawDelta) ? Math.min(.05, Math.max(0, rawDelta)) : 0;
        const elapsed = this.clock.getElapsedTime();
        if(this.live2d){this.reactionExpressions?.update(delta);this.autoExpressions?.update(delta);this._applyCollaboratorPose();this.live2d.render(delta);return;}
        this._prepareCompanionSurface();

        // RGB Aura / Breathing cycle
        if (this.rgbBreathing) {
            const hue = (elapsed * 0.05) % 1;
            const rgbColor = new THREE.Color().setHSL(hue, 0.9, 0.6);
            if (this.rimLight) {
                this.rimLight.color.copy(rgbColor);
                this.rimLight.intensity = 0.9 * this.envIntensity;
            }
            if (this.groundLight) {
                this.groundLight.color.copy(rgbColor);
                this.groundLight.intensity = 0.4 * this.envIntensity;
            }
            if (this.placeholderMesh && this.placeholderMesh.material) {
                this.placeholderMesh.material.color.copy(rgbColor);
                this.placeholderMesh.material.emissive.copy(rgbColor);
            }
            if (this.onColorChange) {
                const hex = '#' + rgbColor.getHexString();
                this.onColorChange(hex);
            }
        }

        // Idle placeholder animation
        if (this.placeholderGroup) {
            this.placeholderMesh.rotation.y += delta * 0.5;
            this.placeholderMesh.rotation.x += delta * 0.25;
            this.innerOrb.scale.setScalar(1 + Math.sin(elapsed * 2.5) * 0.08);
        }

        // Natural idle eye blink when model is loaded
        if (this._shouldAutoBlink() && this.model && this.resolvedVowels['Blink']) {
            this.blinkTimer += delta;
            if (!this.isBlinking && this.blinkTimer > this.nextBlinkTime) {
                this.isBlinking = true;
                this.blinkProgress = 0;
            }

            if (this.isBlinking) {
                this.blinkProgress += delta * 7.0; // blink duration ~0.25s
                if (this.blinkProgress >= Math.PI) {
                    this.isBlinking = false;
                    this.setMorph('Blink', 0);
                    this.blinkTimer = 0;
                    this.nextBlinkTime = 2.5 + Math.random() * 4.0;
                } else {
                    const weight = Math.sin(this.blinkProgress);
                    this.setMorph('Blink', weight);
                }
            }
        }

        this._restoreCursorHeadPose();
        restoreIdleBreathing(this);
        this._animateCharacter(delta, elapsed);
        this.boneControls?.apply();
        applyIdleBreathing(this, delta, elapsed);
        this.reactionExpressions?.update(delta);
        this.autoExpressions?.update(delta);
        // Apply after webcam/idle morphs so tracking cannot overwrite the
        // explicitly selected expression on the following frame.
        if(!this.areAiExpressionsAutomatic?.()&&this.manualExpressions?.size) {
            for(const [name,weight]of this.manualExpressions){
                const custom=this.customExpressions?.[name];
                if(custom&&!this.live2d)for(const p of custom.parameters)this.setMorph(p.id,p.value*weight);
                else this.setMorph(name,weight);
            }
        } else if (!this.areAiExpressionsAutomatic?.() && this.manualExpression)
            this.setMorph(this.manualExpression.name, this.manualExpression.weight);
        // Physics runs after the gesture poses are written so hair, clothing
        applyVisibility(this);
        // and body chains inherit their motion as inertia this frame.
        this.physics.updateSpeechPhysics(this.userTracking ? (this.avatarRetarget?.weights?.A || 0)
            : this.activity === 'talking' ? this.speechLevel : 0, delta);
        this.physics.update(delta);
        if (this._shouldUseCursorGaze()) this._animateEyeTracking(delta);
        if (this.vrm) this.vrm.update(delta);
        this.rigMonitor?.enforce();
        this.rigMonitor?.sample();
        this.boneControls?.apply();
        this.controls.update();
        this._applyCollaboratorPose();
        if (this.characterGlow > 0 && this.bloomPass) {
            this.renderer.setRenderTarget(this.bloomBase);
            this.renderer.clear();
            if(this.characterLightingTarget&&this._bloomTargetObjects?.length){
                const bloomLayer=31,cameraMask=this.camera.layers.mask,background=this.scene.background;
                const changed=[];
                for(const object of [...this._bloomTargetObjects,...(this._bloomLights||[])]){changed.push([object,object.layers.mask]);object.layers.enable(bloomLayer);}
                this.camera.layers.set(bloomLayer);this._blackBloomBackground||=new THREE.Color(0x000000);this.scene.background=this._blackBloomBackground;
                try{this.renderer.render(this.scene,this.camera);}
                finally{this.camera.layers.mask=cameraMask;this.scene.background=background;for(const [object,mask]of changed)object.layers.mask=mask;}
            }else this.renderer.render(this.scene, this.camera);
            this.bloomCopy.material.uniforms.image.value = this.bloomBase.texture;
            this.renderer.setRenderTarget(this.bloomWork);
            this.bloomCopy.render(this.renderer);
            this.bloomPass.render(this.renderer, null, this.bloomWork, delta, false);
            this.renderer.setRenderTarget(null);
            this.renderer.render(this.scene, this.camera);
            const oldAutoClear = this.renderer.autoClear;
            this.renderer.autoClear = false;
            this.bloomFinal.render(this.renderer);
            this.renderer.autoClear = oldAutoClear;
        } else this.renderer.render(this.scene, this.camera);
    }
}
