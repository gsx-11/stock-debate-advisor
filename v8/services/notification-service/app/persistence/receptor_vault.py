from fastcrud import FastCRUD
from sqlalchemy.ext.asyncio import AsyncSession

from app.persistence.receptor_record import ReceptorRecord


class ReceptorVault:
    """Vault operations for receptor management"""
    
    def __init__(self, vault_session: AsyncSession):
        self.vault_session = vault_session
        self.rapid_accessor = FastCRUD(ReceptorRecord)
    
    async def inscribe_receptor(
        self,
        receptor_id: str,
        pathway_name: str,
        subject_name: str
    ) -> ReceptorRecord:
        """Inscribe new receptor into vault"""
        inscription_blueprint = {
            "receptor_identity": receptor_id,
            "conduit_pathway": pathway_name,
            "subject_matter": subject_name
        }
        
        inscribed_entity = await self.rapid_accessor.create(
            db=self.vault_session,
            object=inscription_blueprint
        )
        
        await self.vault_session.commit()
        
        return inscribed_entity
    
    async def retrieve_receptor_pathways(
        self,
        receptor_id: str
    ) -> list[ReceptorRecord]:
        """Retrieve all pathways for receptor"""
        extraction_result = await self.rapid_accessor.get_multi(
            db=self.vault_session,
            receptor_identity=receptor_id
        )
        
        return extraction_result.get("data", [])
    
    async def retrieve_subject_receptors(
        self,
        subject_name: str
    ) -> list[ReceptorRecord]:
        """Retrieve all receptors for subject"""
        extraction_result = await self.rapid_accessor.get_multi(
            db=self.vault_session,
            subject_matter=subject_name
        )
        
        return extraction_result.get("data", [])
