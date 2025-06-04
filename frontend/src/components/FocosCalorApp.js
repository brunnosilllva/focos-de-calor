# Adicionar esta função ao seu script existente (no final)

def save_public_link_for_website(self, file_id):
    """Salva o link público para o site React usar"""
    try:
        # Tornar o arquivo público (se ainda não for)
        self.drive_service.permissions().create(
            fileId=file_id,
            body={'role': 'reader', 'type': 'anyone'}
        ).execute()
        
        # Gerar link direto para download
        public_link = f"https://drive.google.com/uc?id={file_id}&export=download"
        
        # Criar informações para o site
        link_info = {
            "public_url": public_link,
            "file_id": file_id,
            "filename": "focos_qualificados_atual.xlsx",
            "last_updated": datetime.now().isoformat(),
            "total_records": len(self.dados_processados) if hasattr(self, 'dados_processados') else 0,
            "description": "Dados de focos de calor do Maranhão processados automaticamente",
            "source": "INPE",
            "processor": "IMESC"
        }
        
        # Criar diretório data se não existir
        os.makedirs('data', exist_ok=True)
        
        # Salvar link para o site React usar
        with open('data/current_data_link.json', 'w', encoding='utf-8') as f:
            json.dump(link_info, f, indent=2, ensure_ascii=False)
            
        print(f"✅ Link público salvo: {public_link}")
        print(f"📁 Arquivo disponível em: data/current_data_link.json")
        
        return public_link
        
    except Exception as e:
        print(f"❌ Erro ao salvar link público: {e}")
        return None

# Modificar sua função update_main_file para incluir isso:
def update_main_file(self, local_path, folder_id, filename):
    """Atualiza o arquivo principal (mesmo ID, conteúdo novo)"""
    try:
        # Seu código existente...
        
        if files:
            # Atualizar arquivo existente
            file_id = files[0]['id']
            media = MediaFileUpload(local_path, resumable=True)
            updated_file = self.drive_service.files().update(
                fileId=file_id, media_body=media
            ).execute()
            print(f"   ✅ Arquivo principal atualizado: {filename} (ID: {file_id})")
            
            # NOVA LINHA: Salvar link para o site
            self.save_public_link_for_website(file_id)
            
            return file_id
        else:
            # Criar novo arquivo principal
            file_metadata = {'name': filename, 'parents': [folder_id]}
            media = MediaFileUpload(local_path, resumable=True)
            file = self.drive_service.files().create(
                body=file_metadata, media_body=media, fields='id,name'
            ).execute()
            file_id = file.get('id')
            print(f"   ✅ Arquivo principal criado: {filename} (ID: {file_id})")
            
            # NOVA LINHA: Salvar link para o site
            self.save_public_link_for_website(file_id)
            
            return file_id
            
    except Exception as e:
        print(f"   ❌ Erro ao atualizar arquivo principal: {e}")
        return None
