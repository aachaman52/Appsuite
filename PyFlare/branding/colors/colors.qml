import QtQuick 2.15

QtObject {
    readonly property color primary: "#3B82F6"
    readonly property color cyan: "#00D4FF"
    readonly property color indigo: "#5B5FFF"
    readonly property color violet: "#8A5CF5"
    readonly property color magenta: "#EC4899"
    readonly property color background: "#0B0F19"
    readonly property color surface: "#111827"
    readonly property color border: "#1F2937"
    readonly property color white: "#FFFFFF"
    readonly property color black: "#000000"

    // Gradients (as string descriptors)
    readonly property string primary_gradient: "linear:0%=#5B5FFF;50%=#3B82F6;100%=#00D4FF"
    readonly property string violet_gradient: "linear:0%=#8A5CF5;100%=#5B5FFF"
    readonly property string warm_gradient: "linear:0%=#EC4899;100%=#8A5CF5"
    readonly property string surface_glow: "radial:0%=#1F2937;100%=#0B0F19"
}
