import * as THREE from 'three';

// MMD materials describe legacy colour-space diffuse + ambient lighting.
// Feeding those values through a modern Phong/PI lighting sum makes authored
// pastel colours and white trim grey. Clamp the authored lighting before
// applying the texture, then convert that factor for Three's linear output.
export function applyPmxReferenceLighting(material,authored){
    if(!material?.isMMDToonMaterial||!authored||material.userData?.sakuraPmxReference)return;
    const valid=values=>Array.isArray(values)&&values.length>=3&&values.slice(0,3).every(Number.isFinite);
    if(!valid(authored.diffuse)||!valid(authored.ambient))return;
    const marker=/vec3 outgoingLight = [^;]*totalEmissiveRadiance;/;
    if(!marker.test(material.fragmentShader))return;
    const diffuse=new THREE.Color().setRGB(...authored.diffuse.slice(0,3),THREE.SRGBColorSpace);
    material.diffuse.copy(diffuse);
    material.uniforms.sakuraPmxDiffuse={value:new THREE.Vector3(...authored.diffuse.slice(0,3))};
    material.uniforms.sakuraPmxAmbient={value:new THREE.Vector3(...authored.ambient.slice(0,3))};
    material.uniforms.sakuraPmxOriginalLinear={value:new THREE.Vector3(diffuse.r,diffuse.g,diffuse.b)};
    material.fragmentShader='uniform vec3 sakuraPmxDiffuse, sakuraPmxAmbient, sakuraPmxOriginalLinear;\n'+material.fragmentShader.replace(marker,`
        vec3 sakuraLight = vec3(1.0);
        #if NUM_DIR_LIGHTS > 0
            sakuraLight = getGradientIrradiance(normal, directionalLights[0].direction);
        #endif
        vec3 sakuraFactor = clamp(sakuraPmxAmbient + sakuraPmxDiffuse * (0.6 * sakuraLight), 0.0, 1.0);
        vec3 sakuraLinear = mix(pow((sakuraFactor + 0.055) / 1.055, vec3(2.4)), sakuraFactor / 12.92, lessThanEqual(sakuraFactor,vec3(0.04045)));
        vec3 sakuraTexel = vec3(1.0);
        #ifdef USE_MAP
            sakuraTexel = sampledDiffuseColor.rgb;
        #endif
        vec3 sakuraTint = mix(vec3(1.0), diffuse / max(sakuraPmxOriginalLinear,vec3(0.00001)), step(vec3(0.00001),sakuraPmxOriginalLinear));
        vec3 outgoingLight = sakuraTexel * sakuraLinear * sakuraTint + reflectedLight.directSpecular + reflectedLight.indirectSpecular;
    `).replace('outgoingLight += matcapColor.rgb * 0.12;','outgoingLight += matcapColor.rgb;');
    material.userData.sakuraPmxReference=true;
    material.needsUpdate=true;
}
