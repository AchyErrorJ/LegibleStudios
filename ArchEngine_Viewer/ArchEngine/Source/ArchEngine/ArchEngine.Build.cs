using UnrealBuildTool;
using System.IO;

public class ArchEngineViewer : ModuleRules
{
    public ArchEngineViewer(ReadOnlyTargetRules Target) : base(Target)
    {
        PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;

        // Core Unreal Modules
        PublicDependencyModuleNames.AddRange(new string[] { "Core", "CoreUObject", "Engine", "InputCore", "Json", "JsonUtilities" });

        // --- ARCHENGINE KERNEL BRIDGE ---
        // We reach up one level and over into the Kernel directory
        string KernelIncludePath = Path.Combine(ModuleDirectory, "../../../ArchEngine_Kernel/include");

        if (Directory.Exists(KernelIncludePath))
        {
            PublicIncludePaths.Add(KernelIncludePath);
        }
    }
}