// ArchEngine Viewer - Module implementation

#include "ArchEngine.h"
#include "Modules/ModuleManager.h"

void FArchEngineModule::StartupModule()
{
    UE_LOG(LogTemp, Log, TEXT("ArchEngine Viewer module started"));
}

void FArchEngineModule::ShutdownModule()
{
    UE_LOG(LogTemp, Log, TEXT("ArchEngine Viewer module shutdown"));
}

IMPLEMENT_PRIMARY_GAME_MODULE(FArchEngineModule, ArchEngine, "ArchEngine");
