using UnrealBuildTool;
using System.IO;

public class ArchEngine : ModuleRules
{
    public ArchEngine(ReadOnlyTargetRules Target) : base(Target)
    {
        PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;

        // Core Unreal Modules
        PublicDependencyModuleNames.AddRange(new string[] {
            "Core",
            "CoreUObject",
            "Engine",
            "InputCore",
            "EnhancedInput",
            "UMG",
            "Slate",
            "SlateCore",
            "Json",
            "JsonUtilities",
            "ProceduralMeshComponent",
            "WebSockets",
            "RHI",
            "RenderCore"
        });

        // Platform-specific for D3D11 texture sharing
        if (Target.Platform == UnrealTargetPlatform.Win64)
        {
            PublicSystemLibraries.AddRange(new string[] {
                "d3d11.lib",
                "dxgi.lib"
            });
        }

        // Add module directory so "Types/ArchTypes.h" style includes work
        PublicIncludePaths.Add(ModuleDirectory);

        // --- ARCHENGINE KERNEL BRIDGE ---
        // We reach up one level and over into the Kernel directory
        string KernelIncludePath = Path.Combine(ModuleDirectory, "../../../ArchEngine_kernel/include");

        if (Directory.Exists(KernelIncludePath))
        {
            PublicIncludePaths.Add(KernelIncludePath);
        }
    }
}