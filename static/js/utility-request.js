// Native commands/live lookups do not need screen capture or avatar readback.
export function utilityRequest(text){
    const t=String(text).replace(/’/g,"'").trim().toLowerCase();
    if(/\b(?:on (?:my |the |this |your )?screen|in (?:this|the) (?:image|picture|video)|can you see)\b/u.test(t))return false;
    return /\b(?:cpu usage|gpu usage|vram usage|ram usage|memory usage|pc status|system status|system information|battery level|disk space|volume|show capabilities|list capabilities|find file)\b/u.test(t)
        || /\b(?:weather|forecast|temperature|news|headlines)\b/u.test(t)
        || /\b(?:set|make|create|start|cancel|list|show|stop|dismiss|snooze)\b.*\b(?:timers?|alarms?)\b/u.test(t)
        || /\b(?:open|launch|start)\s+\S/u.test(t)
        || /^(?:(?:hey\s+)?sakura[,!\s]+)?(?:(?:can|could|would)\s+(?:you|u)\s+(?:please\s+)?|please\s+)?(?:(?:tell|give)\s+me\s+(?:what\s+)?)?(?:(?:what(?:'s| is)\s+)?(?:the\s+)?(?:current\s+|local\s+)?(?:time|date)(?:\s+(?:is it|it is|now|right now|today))?|what time is it|what day is (?:it|today)|what(?:'s| is) today's date)[?!.\s]*$/u.test(t);
}
