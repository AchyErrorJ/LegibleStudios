#include <include/types.hpp>
#include <iostream>

using namespace arch;

int main() {
    std::cout << "=== UniformBufferObject Layout Analysis ===" << std::endl;
    std::cout << "Size of UniformBufferObject: " << sizeof(UniformBufferObject) << " bytes" << std::endl;
    std::cout << std::endl;

    std::cout << "Field offsets (C++ offsetof):" << std::endl;
    std::cout << "  view:             " << offsetof(UniformBufferObject, view) << std::endl;
    std::cout << "  proj:             " << offsetof(UniformBufferObject, proj) << std::endl;
    std::cout << "  lightViewProj:    " << offsetof(UniformBufferObject, lightViewProj) << std::endl;
    std::cout << "  lightDirection:   " << offsetof(UniformBufferObject, lightDirection) << std::endl;
    std::cout << "  clipPlane:        " << offsetof(UniformBufferObject, clipPlane) << std::endl;
    std::cout << "  time:             " << offsetof(UniformBufferObject, time) << std::endl;
    std::cout << "  shadowBias:       " << offsetof(UniformBufferObject, shadowBias) << std::endl;
    std::cout << "  enableClipping:   " << offsetof(UniformBufferObject, enableClipping) << std::endl;
    std::cout << "  enableShadows:    " << offsetof(UniformBufferObject, enableShadows) << std::endl;
    std::cout << "  outputLinearHDR:  " << offsetof(UniformBufferObject, outputLinearHDR) << std::endl;
    std::cout << "  exposure:         " << offsetof(UniformBufferObject, exposure) << std::endl;
    std::cout << "  tessellationLevel:" << offsetof(UniformBufferObject, tessellationLevel) << std::endl;
    std::cout << "  displacementScale:" << offsetof(UniformBufferObject, displacementScale) << std::endl;
    std::cout << "  materialParams:   " << offsetof(UniformBufferObject, materialParams) << std::endl;
    std::cout << "  materialParams2:  " << offsetof(UniformBufferObject, materialParams2) << std::endl;
    std::cout << "  materialTint:     " << offsetof(UniformBufferObject, materialTint) << std::endl;
    std::cout << "  overrideMask:     " << offsetof(UniformBufferObject, overrideMask) << std::endl;
    std::cout << "  _pad1:            " << offsetof(UniformBufferObject, _pad1) << std::endl;
    std::cout << "  _pad2:            " << offsetof(UniformBufferObject, _pad2) << std::endl;
    std::cout << "  _pad3:            " << offsetof(UniformBufferObject, _pad3) << std::endl;
    std::cout << "  elementOverride1: " << offsetof(UniformBufferObject, elementOverride1) << std::endl;
    std::cout << "  elementOverride2: " << offsetof(UniformBufferObject, elementOverride2) << std::endl;
    std::cout << "  elementOverride3: " << offsetof(UniformBufferObject, elementOverride3) << std::endl;

    std::cout << std::endl;
    std::cout << "Expected std140 offsets:" << std::endl;
    std::cout << "  view:             0" << std::endl;
    std::cout << "  proj:             64" << std::endl;
    std::cout << "  lightViewProj:    128" << std::endl;
    std::cout << "  lightDirection:   192" << std::endl;
    std::cout << "  clipPlane:        208" << std::endl;
    std::cout << "  time:             224" << std::endl;
    std::cout << "  shadowBias:       228" << std::endl;
    std::cout << "  enableClipping:   232" << std::endl;
    std::cout << "  enableShadows:    236" << std::endl;
    std::cout << "  outputLinearHDR:  240" << std::endl;
    std::cout << "  exposure:         244" << std::endl;
    std::cout << "  tessellationLevel:248" << std::endl;
    std::cout << "  displacementScale:252" << std::endl;
    std::cout << "  materialParams:   256" << std::endl;
    std::cout << "  materialParams2:  272" << std::endl;
    std::cout << "  materialTint:     288" << std::endl;
    std::cout << "  overrideMask:     304" << std::endl;
    std::cout << "  _pad1:            308" << std::endl;
    std::cout << "  _pad2:            312" << std::endl;
    std::cout << "  _pad3:            316" << std::endl;
    std::cout << "  elementOverride1: 320" << std::endl;
    std::cout << "  elementOverride2: 336" << std::endl;
    std::cout << "  elementOverride3: 352" << std::endl;

    return 0;
}
