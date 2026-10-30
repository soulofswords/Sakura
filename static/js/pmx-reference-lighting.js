import {normalizePmxAppearance} from './pmx-render-controls.js?v=3';
import * as THREE from 'three';

// PMX files author lighting as raw 0-255 numbers: the texture texel, the material's
// ambient and diffuse, and the toon ramp are combined in that same space and the
// result is shown as the pixel, with no gamma step of its own. Three decodes each
// texture to linear, runs a physically scaled light sum and encodes once at the end,
// so the authored pastels arrive too dark or too grey. This override keeps every term
// in the file's own numbers: recover the raw texel, apply the authored ambient and
// diffuse, then emit the inverse transfer so Three's output encode does not apply
// gamma a second time.
// That is the reference arithmetic, not a pixel match of PMX Editor's viewport. Its
// default here is a flat anime presentation - the authored ambient carries the fill
// and the continuous normal-lighting sculpting stays off until the Directional
// shading slider raises it - and every term is a per-model slider, so a user can move
// Sakura toward a given editor screenshot rather than the other way round. Verified
// against the file's own numbers and real GPU output; not against editor pixels, which
// Sakura has no way to read.
// Nothing here depends on a material or model name.
const sRGBToLinear = 'vec3 sakuraToLinear(vec3 value){return mix(pow((value+vec3(0.055))/1.055,vec3(2.4)),value/12.92,lessThanEqual(value,vec3(0.04045)));}';
const linearToSRGB = 'vec3 sakuraToRaw(vec3 value){return mix(pow(value,vec3(1.0/2.4))*1.055-0.055,value*12.92,lessThanEqual(value,vec3(0.0031308)));}';

// Every texture slot the reference shader branches on must hold a decodable image.
// A slot can be empty two ways: the bytes never decoded (the texture is still
// "present", so the shader keeps its sampling branch), or the loader assigned
// nothing at all. Either way WebGL answers a sample of an unbound or incomplete
// texture with zeros, silently, and PMX multiplies by the texel - so an unreadable
// diffuse map blackens the surface outright, and an empty ramp slot collapses it
// onto the ambient term alone. (An empty ramp does not compile a ramp-free program:
// the presence of a gradientMap is not part of three's cache key, so every toon
// material of a model shares the branch chosen by whichever one compiled first.)
// A face authored at ambient 0.5 then renders at
// exactly half its texture colour, which is the grey mask people see.
// PMX's shared default toon (toonIndex -1) is a white ramp in the loader's own
// built-in set, and a missing diffuse has no colour of its own to fall back to, so
// white is the neutral for both: it lands the authored colour flat, the closest the
// reference renderer gets for an asset that is simply not there.
// Callers must run this after the loader's own onLoad has settled: until then an
// absent image only means still-decoding, and replacing it would discard a good map.
function isDecodable(texture) {
    const image = texture?.image;
    if (!texture?.isTexture || !image) return false;
    if (image.complete === false) return false;
    const width = image.naturalWidth || image.width, height = image.naturalHeight || image.height;
    return Number.isFinite(width) && width > 0 && Number.isFinite(height) && height > 0;
}

const fallbacks = {};
function neutralTexture(name, byte) {
    if (!fallbacks[name]) {
        const texture = new THREE.DataTexture(new Uint8Array([byte, byte, byte, 255]), 1, 1, THREE.RGBAFormat);
        texture.colorSpace = THREE.SRGBColorSpace;
        texture.magFilter = texture.minFilter = THREE.NearestFilter;
        texture.wrapS = texture.wrapT = THREE.ClampToEdgeWrapping;
        texture.generateMipmaps = false;
        texture.flipY = false;
        texture.userData.sakuraPmxFallback = name;
        texture.needsUpdate = true;
        fallbacks[name] = texture;
    }
    return fallbacks[name];
}

export function ensureDecodableMaps(material) {
    if (!material) return null;
    const repaired = [];
    // A zero-filled or truncated file on disk reaches here as a Texture with no
    // image, which is exactly the case that turns a whole head into a silhouette.
    if (material.map && !isDecodable(material.map)) {
        material.map = neutralTexture('diffuse', 255);
        repaired.push('diffuse');
    }
    const ramp = material.gradientMap;
    if (!ramp || !isDecodable(ramp)) {
        material.gradientMap = neutralTexture('toon', 255);
        // A ramp that exists but never decoded is a missing asset; one that was never
        // assigned is the file asking for MMD's shared default, which is flat white.
        repaired.push(ramp ? 'toon' : 'defaultToon');
    }
    if (material.matcap && !isDecodable(material.matcap)) {
        material.matcap = neutralTexture(material.defines?.MATCAP_BLENDING_MULTIPLY ? 'sphereMultiply' : 'sphereAdd',
            material.defines?.MATCAP_BLENDING_MULTIPLY ? 255 : 0);
        repaired.push('sphere');
    }
    return repaired.length ? repaired : null;
}

export function applyPmxReferenceLighting(material, authored) {
    if (!material?.isMMDToonMaterial || material.userData?.sakuraPmxReference) return;
    // Runs even when the authored numbers are unusable below: three's own toon branch
    // collapses to the same black on an undecodable strip.
    const repaired = ensureDecodableMaps(material);
    if (repaired) (material.userData.sakuraPmxRepairs ||= []).push(...repaired);
    if (!authored) return;
    const valid = values => Array.isArray(values) && values.length >= 3 && values.slice(0, 3).every(Number.isFinite);
    if (!valid(authored.diffuse) || !valid(authored.ambient)) return;
    const marker = /vec3 outgoingLight = [^;]*totalEmissiveRadiance;/;
    if (!marker.test(material.fragmentShader)) return;
    // A toon strip is a lookup table, not a repeating tile: the lit end of the
    // ramp sits in the last texel, but halfLambert reaches exactly 1.0 there and
    // RepeatWrapping folds that back onto the first, darkest texel.
    if (material.gradientMap) {
        material.gradientMap.wrapS = material.gradientMap.wrapT = THREE.ClampToEdgeWrapping;
        material.gradientMap.needsUpdate = true;
    }
    const raw = values => new THREE.Vector3(...values.slice(0, 3));
    material.uniforms.sakuraPmxDiffuse = { value: raw(authored.diffuse) };
    material.uniforms.sakuraPmxAmbient = { value: raw(authored.ambient) };
    material.uniforms.sakuraPmxLitAmbient = {value: Math.max(...authored.ambient.slice(0,3))>.002 ? 1 : 0};
    for(const [key,value]of Object.entries(normalizePmxAppearance()))material.uniforms['sakuraPmxControl_'+key]={value};
    const controlUniforms='uniform float sakuraPmxLitAmbient;\n'+'uniform float '+Object.keys(normalizePmxAppearance()).map(key=>'sakuraPmxControl_'+key).join(', ')+';\n';
    material.fragmentShader =
        controlUniforms + 'uniform vec3 sakuraPmxDiffuse, sakuraPmxAmbient;\n' + sRGBToLinear + '\n' + linearToSRGB + '\n' +
        material.fragmentShader.replace(marker, `
            vec3 sakuraTexel = vec3( 1.0 );
            #ifdef USE_MAP
                sakuraTexel = sakuraToRaw( sampledDiffuseColor.rgb );
            #endif
            vec3 sakuraRamp = vec3( 1.0 );
            float sakuraDot = 0.0;
            float sakuraLit = 0.0;
            #if NUM_DIR_LIGHTS > 0
                // PMX authors one sun. A stage can carry several directional lights -
                // Sakura's carries fill lights at zero intensity - and the renderer's
                // sort decides which of them lands in slot 0, so the ramp has to follow
                // the light that actually illuminates the surface rather than whichever
                // happens to be first. A stage with no lit directional light keeps the
                // authored colour instead of collapsing to the darkest ramp band.
                float sakuraBest = 0.0;
                vec3 sakuraSun = vec3( 0.0, 1.0, 0.0 );
                for ( int sakuraIndex = 0; sakuraIndex < NUM_DIR_LIGHTS; sakuraIndex ++ ) {
                    float sakuraStrength = dot( directionalLights[ sakuraIndex ].color, vec3( 0.333333 ) );
                    if ( sakuraStrength > sakuraBest ) {
                        sakuraBest = sakuraStrength;
                        sakuraSun = directionalLights[ sakuraIndex ].direction;
                    }
                }
                if ( sakuraBest > 0.0 ) {
                    sakuraDot = dot( normal, normalize( sakuraSun ) );
                    sakuraLit = clamp( sakuraDot, 0.0, 1.0 );
                    #ifdef USE_GRADIENTMAP
                        // PMX Editor's ToonSampler multiplies all three colour
                        // channels. Reading only red destroys coloured ramps.
                        sakuraRamp = sakuraToRaw( texture2D( gradientMap, vec2( clamp( sakuraDot * 0.5 + 0.5, 0.0, 1.0 ), 0.0 ) ).rgb );
                    #endif
                }
            #endif
            // Flat presentation still needs the neutral key light: ambient
            // alone is the authored shadow colour, not the base albedo.
            // Keep zero-ambient dark materials unchanged. Directional mode
            // replaces this flat key with NdotL instead of adding another light.
            float sakuraKey = mix(0.5 * sakuraPmxLitAmbient * sakuraPmxControl_ambient, sakuraLit, sakuraPmxControl_normal);
            vec3 sakuraFill = sakuraPmxAmbient * sakuraPmxControl_ambient + vec3(0.5 * sakuraKey);
            vec3 sakuraFactor = clamp( sakuraFill * 2.0 * mix(vec3(1.0), sakuraPmxDiffuse, sakuraPmxControl_diffuse), 0.0, 1.0 );
            vec3 sakuraRaw = clamp( sakuraTexel * sakuraFactor, 0.0, 1.0 );
            // Three's own Blinn-Phong term is driven by the half-lambert gradient irradiance,
            // so it survives on faces turned away from the light and paints a highlight where
            // the reference shows shade. PMX gives its specular only where the surface actually
            // receives the ray, and adds it in the same raw space as everything else, so gate it
            // by the true cosine and composite it before the single clamp and encode.
            vec3 sakuraSpecular = sakuraPmxControl_specular * step(0.98, sakuraLit) * min(vec3(0.15), sakuraToRaw( reflectedLight.directSpecular + reflectedLight.indirectSpecular ));
            vec3 outgoingLight = sakuraToLinear( clamp( sakuraRaw + sakuraSpecular, 0.0, 1.0 ) );
        `)
            // PMX's sub-texture (sphere map) combines with the lit colour in the same raw
            // space as everything else, so it has to be undone, combined and redone; and an
            // additive sphere contribution is added independently of the base
            // texel, as in PMX Editor's SphereMode=2 shader branch.
            .replace('outgoingLight *= matcapColor.rgb;',
                'outgoingLight = sakuraToLinear( clamp( sakuraToRaw( outgoingLight ) * mix(vec3(1.0), sakuraToRaw( matcapColor.rgb ), sakuraPmxControl_sphere), 0.0, 1.0 ) );')
            .replace(/outgoingLight \+= matcapColor\.rgb[^;]*;/,
                'outgoingLight = sakuraToLinear( clamp( sakuraToRaw( outgoingLight ) + sakuraPmxControl_sphere * sakuraToRaw( matcapColor.rgb ), 0.0, 1.0 ) );');
    // The editor combines sphere and base first, then multiplies by toon.
    // Adding coloured shine after toon left it entirely unattenuated.
    material.fragmentShader=material.fragmentShader.replace('#include <opaque_fragment>', `
        outgoingLight=sakuraToLinear(clamp(sakuraToRaw(outgoingLight)*mix(vec3(1.0),sakuraRamp,sakuraPmxControl_toon),0.0,1.0));
        #include <opaque_fragment>
    `);
    material.fragmentShader=material.fragmentShader.replace('#include <tonemapping_fragment>', `
        vec3 sakuraFinal = sakuraToRaw(max(outgoingLight,vec3(0.0)));
        float sakuraLuma = dot(sakuraFinal,vec3(0.2126,0.7152,0.0722));
        outgoingLight = sakuraToLinear(clamp(mix(vec3(sakuraLuma),sakuraFinal,sakuraPmxControl_saturation)*sakuraPmxControl_brightness,0.0,1.0));
        #include <tonemapping_fragment>
    `.replaceAll('outgoingLight','gl_FragColor.rgb'));
    material.userData.sakuraPmxReference = true;
    material.needsUpdate = true;
}
