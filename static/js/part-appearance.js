// Tint and opacity edits preserve the other channel's saved value.
export function tintEdit(current,color,strength){
    return {color,strength,opacity:current?.opacity??1};
}
export function opacityEdit(current,opacity){
    return {color:current?.color||'#ffffff',strength:current?.strength??0,opacity};
}
