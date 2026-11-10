// GN_physarum deposit, GLSL MAT pixel shader: rgb = deposit into the agent's species channel, a = 1 (agent count).
in Vertex { vec4 color; } iV;
layout(location = 0) out vec4 fragColor;

void main()
{
	fragColor = iV.color;
}
