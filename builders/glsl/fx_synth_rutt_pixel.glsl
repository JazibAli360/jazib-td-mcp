// FX_synth ruttetra, GLSL MAT pixel shader: anti-aliased beam of Width px across the ribbon (the vertex shader
// widened it by 1 px each side), premultiplied, drawn additively (src one, dst one): crossings and dense lines pile up
// like a real beam. Width < 1 fades instead of thinning further.
uniform vec4 uA;   // lines, samples, width px, intensity
in Vertex { vec4 color; float across; } iVert;
layout(location = 0) out vec4 fragColor;
void main() {
    TDCheckDiscard();
    float cov = clamp(uA.z * 0.5 + 0.5 - abs(iVert.across), 0.0, 1.0) * min(uA.z, 1.0);
    fragColor = TDOutputSwizzle(iVert.color * cov);
}
