from app.adapters.openai_realtime_adapter import OpenAIRealtimeAdapter
from app.adapters.openai_realtime_sideband_adapter import OpenAIRealtimeSidebandAdapter
from app.adapters.voice_adapter import VoiceAdapter
from app.services.assistant_service import AssistantService
from app.services.conversation_repository import InMemoryConversationRepository
from app.services.conversation_service import ConversationService
from app.services.handoff_service import HandoffService
from app.services.notification_service import NotificationService
from app.services.practice_info_service import PracticeInfoService
from app.services.provider_matching_service import ProviderMatchingService
from app.services.realtime_voice_service import RealtimeVoiceService
from app.services.refill_service import RefillService
from app.services.safety_service import SafetyService
from app.services.scheduling_service import SchedulingService
from app.services.twilio_media_bridge import TwilioMediaBridge
from app.services.voice_sip_service import VoiceSipService

conversation_repository = InMemoryConversationRepository()
conversation_service = ConversationService(repository=conversation_repository)
provider_matching_service = ProviderMatchingService()
scheduling_service = SchedulingService()
safety_service = SafetyService()
assistant_service = AssistantService(safety_service=safety_service)
notification_service = NotificationService()
practice_info_service = PracticeInfoService()
refill_service = RefillService()
voice_adapter = VoiceAdapter()
handoff_service = HandoffService(
    conversation_service=conversation_service,
    scheduling_service=scheduling_service,
    voice_adapter=voice_adapter,
)
realtime_voice_service = RealtimeVoiceService(handoff_service=handoff_service)
voice_sip_service = VoiceSipService(
    handoff_service=handoff_service,
    realtime_voice_service=realtime_voice_service,
)
openai_realtime_adapter = OpenAIRealtimeAdapter()
openai_realtime_sideband_adapter = OpenAIRealtimeSidebandAdapter()
twilio_media_bridge = TwilioMediaBridge(
    realtime_voice_service=realtime_voice_service,
    openai_realtime_adapter=openai_realtime_adapter,
)
