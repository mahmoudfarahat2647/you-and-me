import type { StageId } from '@/types';
import type { ProviderCapability, ProviderConfigSummary } from '@/types/providers';

export const STAGE_PROVIDER_CAPABILITY: Partial<Record<StageId, ProviderCapability>> = {
  idea: 'research',
  script: 'text_generation',
  voice: 'tts',
  scenes: 'video_generation',
};

export function isProviderReady(provider: ProviderConfigSummary, stageId: StageId): boolean {
  const capability = STAGE_PROVIDER_CAPABILITY[stageId];
  return Boolean(
    capability && provider.supported_capabilities.includes(capability) &&
    provider.connection_status === 'verified' && provider.credential_status !== 'missing' &&
    provider.selected_model && provider.verified_models.includes(provider.selected_model)
  );
}
