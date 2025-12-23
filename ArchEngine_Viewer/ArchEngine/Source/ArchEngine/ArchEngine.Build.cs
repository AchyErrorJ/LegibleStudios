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
            "Json",
            "JsonUtilities",
            "ProceduralMeshComponent",
            "WebSockets"
        });

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