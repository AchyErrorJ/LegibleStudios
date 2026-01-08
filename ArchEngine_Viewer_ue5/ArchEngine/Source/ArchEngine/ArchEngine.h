// ArchEngine Viewer - Unreal Engine visualization for ArchEngine Suite

#pragma once

#include "CoreMinimal.h"
#include "Modules/ModuleManager.h"

class FArchEngineModule : public IModuleInterface
{
public:
    virtual void StartupModule() override;
    virtual void ShutdownModule() override;
};
