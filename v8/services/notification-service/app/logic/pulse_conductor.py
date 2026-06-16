from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession

from app.persistence.receptor_vault import ReceptorVault
from app.logic.conduit_nexus import conduit_nexus_singleton


class PulseConductor:
    """Conducts pulse transmission and receptor orchestration"""
    
    def __init__(self, vault_session: AsyncSession):
        self.vault_session = vault_session
        self.vault = ReceptorVault(vault_session)
    
    async def orchestrate_receptor_enrollment(
        self,
        receptor_id: str,
        pathway_designation: str,
        subject_designation: str
    ) -> dict:
        """Orchestrate receptor enrollment and return manifest"""
        
        enrollment_record = await self.vault.inscribe_receptor(
            receptor_id=receptor_id,
            pathway_name=pathway_designation,
            subject_name=subject_designation
        )
        
        await self._transmit_enrollment_acknowledgment(
            receptor_id=receptor_id,
            pathway_name=pathway_designation,
            subject_name=subject_designation
        )
        
        return {
            "enrollment_id": enrollment_record.id,
            "receptor": receptor_id,
            "pathway": pathway_designation,
            "subject": subject_designation,
            "enrollment_status": "operational",
            "inscribed_at": enrollment_record.inscription_moment.isoformat()
        }
    
    async def _transmit_enrollment_acknowledgment(
        self,
        receptor_id: str,
        pathway_name: str,
        subject_name: str
    ):
        """Transmit acknowledgment pulse via conduit"""
        acknowledgment_pulse = {
            "pulse_category": "enrollment_acknowledgment",
            "pathway": pathway_name,
            "subject": subject_name,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "beacon_text": f"Enrollment confirmed for {subject_name} via {pathway_name}"
        }
        
        await conduit_nexus_singleton.transmit_pulse_to_receptor(
            receptor_id=receptor_id,
            pulse_cargo=acknowledgment_pulse
        )
    
    async def propagate_subject_beacon(
        self,
        subject_designation: str,
        beacon_cargo: dict
    ):
        """Propagate beacon to all subject receptors"""
        
        subject_receptors = await self.vault.retrieve_subject_receptors(
            subject_name=subject_designation
        )
        
        receptor_identities = list(set(rec.receptor_identity for rec in subject_receptors))
        
        enriched_cargo = {
            **beacon_cargo,
            "subject": subject_designation,
            "propagation_moment": datetime.now(timezone.utc).isoformat()
        }
        
        await conduit_nexus_singleton.broadcast_pulse_cascade(
            receptor_roster=receptor_identities,
            pulse_cargo=enriched_cargo
        )
