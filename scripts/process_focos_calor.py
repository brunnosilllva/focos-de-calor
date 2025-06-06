import os
import pandas as pd
import geopandas as gpd
from shapely.geometry import Point
import tempfile
import shutil
from datetime import datetime
import json
import io

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload, MediaFileUpload

class FocosCalorProcessor:
    def __init__(self, credentials_path='credentials.json'):
        """Inicializa o processador com as credenciais do Google Drive"""
        self.setup_drive_service(credentials_path)
        self.temp_dir = tempfile.mkdtemp()
        self.dados_processados = None  # Para rastrear dados processados
        print(f"📁 Diretório temporário criado: {self.temp_dir}")
        
    def setup_drive_service(self, credentials_path):
        """Configura o serviço do Google Drive"""
        creds = Credentials.from_service_account_file(
            credentials_path,
            scopes=['https://www.googleapis.com/auth/drive']
        )
        self.drive_service = build('drive', 'v3', credentials=creds)
        print("✅ Conexão com Google Drive estabelecida")
        
    def find_folder_by_path(self, folder_path):
        """Encontra pastas pelo nome"""
        print("🔍 Buscando pastas no Google Drive...")
        
        folders_map = {
            "1. Focos": None,
            "2. Referências Espaciais": None,
            "3. Resultados": None
        }
        
        # Buscar TODAS as pastas acessíveis
        results = self.drive_service.files().list(
            q="mimeType='application/vnd.google-apps.folder'",
            fields="files(id, name, parents)"
        ).execute()
        
        print(f"📂 Total de pastas encontradas: {len(results.get('files', []))}")
        
        for folder in results.get('files', []):
            folder_name = folder['name']
            
            # Verificação exata e parcial
            if folder_name in folders_map:
                folders_map[folder_name] = folder['id']
                print(f"✅ Pasta encontrada: {folder_name}")
            elif "Focos" in folder_name or "focos" in folder_name:
                folders_map["1. Focos"] = folder['id']
                print(f"✅ Pasta de focos encontrada: {folder_name}")
            elif "Referências" in folder_name or "referencias" in folder_name:
                folders_map["2. Referências Espaciais"] = folder['id']
                print(f"✅ Pasta de referências encontrada: {folder_name}")
            elif "Resultados" in folder_name or "resultados" in folder_name:
                folders_map["3. Resultados"] = folder['id']
                print(f"✅ Pasta de resultados encontrada: {folder_name}")
                
        print(f"📋 Mapeamento final: {folders_map}")
        return folders_map
        
    def download_all_csv_files(self, folder_id):
        """Baixa TODOS os arquivos CSV da pasta, independente do tamanho"""
        print("📥 Baixando TODOS os arquivos CSV...")
        
        # Buscar TODOS os arquivos CSV
        query = f"'{folder_id}' in parents and name contains '.csv' and trashed=false"
        results = self.drive_service.files().list(
            q=query,
            fields="files(id, name, size)",
            pageSize=1000  # Aumentar limite para pegar todos
        ).execute()
        
        files = results.get('files', [])
        downloaded_files = []
        
        print(f"🔍 Encontrados {len(files)} arquivos CSV")
        
        for file_info in files:
            file_name = file_info['name']
            file_size = int(file_info.get('size', 0))
            
            local_path = os.path.join(self.temp_dir, 'focos', file_name)
            os.makedirs(os.path.dirname(local_path), exist_ok=True)
            
            try:
                self.download_file(file_info['id'], local_path)
                downloaded_files.append(local_path)
                print(f"📥 Baixado: {file_name} ({file_size} bytes)")
            except Exception as e:
                print(f"❌ Erro ao baixar {file_name}: {e}")
                
        print(f"✅ Total baixado: {len(downloaded_files)} arquivos")
        return downloaded_files
        
    def download_file(self, file_id, local_path):
        """Baixa um arquivo específico do Google Drive"""
        request = self.drive_service.files().get_media(fileId=file_id)
        os.makedirs(os.path.dirname(local_path), exist_ok=True)
        with open(local_path, 'wb') as f:
            downloader = MediaIoBaseDownload(f, request)
            done = False
            while done is False:
                status, done = downloader.next_chunk()
                
    def load_and_concat_all_data(self, csv_files):
        """Carrega e concatena TODOS os dados, mesmo arquivos pequenos/vazios"""
        print("🔄 Processando TODOS os arquivos CSV...")
        
        all_dataframes = []
        total_records = 0
        processed_files = 0
        error_files = 0
        
        for csv_file in csv_files:
            file_name = os.path.basename(csv_file)
            try:
                # Tentar ler o arquivo
                df = pd.read_csv(csv_file)
                
                if len(df) > 0:
                    all_dataframes.append(df)
                    total_records += len(df)
                    processed_files += 1
                    print(f"✅ {file_name}: {len(df)} registros")
                else:
                    print(f"⚠️ {file_name}: arquivo vazio")
                    
            except pd.errors.EmptyDataError:
                print(f"⚠️ {file_name}: arquivo vazio (EmptyDataError)")
            except Exception as e:
                error_files += 1
                print(f"❌ {file_name}: erro - {e}")
                
        print(f"\n📊 RESUMO DO PROCESSAMENTO:")
        print(f"   📁 Arquivos processados: {processed_files}")
        print(f"   📊 Total de registros: {total_records}")
        print(f"   ❌ Arquivos com erro: {error_files}")
        
        if not all_dataframes:
            print("❌ NENHUM dado válido encontrado!")
            return None
            
        # Concatenar TODOS os dataframes
        print("🔗 Concatenando todos os dados...")
        df_final = pd.concat(all_dataframes, ignore_index=True)
        
        print(f"✅ Dataset final: {len(df_final)} registros de {len(all_dataframes)} arquivos")
        return df_final
        
    def clean_and_prepare_geodataframe(self, df_focos):
        """Limpa e prepara o GeoDataFrame conforme script original"""
        print("🧹 Limpando e preparando dados...")
        
        # Limpeza conforme script original
        if "Unnamed: 0" in df_focos.columns:
            df_focos.drop(columns=["Unnamed: 0"], inplace=True)
            print("   ✅ Removida coluna 'Unnamed: 0'")
            
        if "M" in df_focos.columns:
            df_focos.rename(columns={"M": "lon"}, inplace=True)
            print("   ✅ Coluna 'M' renomeada para 'lon'")
            
        # Verificar colunas essenciais
        if 'lat' not in df_focos.columns or 'lon' not in df_focos.columns:
            print("❌ Colunas 'lat' e 'lon' não encontradas!")
            print(f"   Colunas disponíveis: {list(df_focos.columns)}")
            return None
            
        # Remover registros sem coordenadas
        antes = len(df_focos)
        df_focos = df_focos.dropna(subset=["lat", "lon"])
        depois = len(df_focos)
        
        if antes != depois:
            print(f"   ⚠️ Removidos {antes - depois} registros sem coordenadas")
            
        if df_focos.empty:
            print("❌ Nenhum registro válido após limpeza!")
            return None
            
        # Criar GeoDataFrame
        print("🌍 Criando GeoDataFrame...")
        gdf_focos = gpd.GeoDataFrame(
            df_focos, 
            geometry=gpd.points_from_xy(df_focos["lon"], df_focos["lat"]), 
            crs="EPSG:4326"
        )
        
        print(f"✅ GeoDataFrame criado: {len(gdf_focos)} pontos válidos")
        return gdf_focos
        
    def download_spatial_references(self, ref_folder_id):
        """Baixa TODAS as referências espaciais disponíveis"""
        print("📍 Baixando referências espaciais...")
        
        # Mapear estrutura esperada
        spatial_mapping = {
            "uf": ["Unidades da Federação", "UF", "Estados", "uf"],
            "municipios": ["Municipios", "municipios", "Municipios_2023"],
            "biomas": ["Biomas", "biomas", "lm_bioma_250"],
            "terras_indigenas": ["Terras Indigenas", "terras_indigenas", "indigenas"],
            "uso_solo": ["Uso do Solo", "uso_solo", "MA_2023_DISSOLVE_REPROJETADO"],
            "zee": ["Zonas do Zee", "zee", "Zonas_atualizada_MA"]
        }
        
        # Buscar subpastas
        subfolders_query = f"'{ref_folder_id}' in parents and mimeType='application/vnd.google-apps.folder' and trashed=false"
        subfolders_results = self.drive_service.files().list(
            q=subfolders_query,
            fields="files(id, name)"
        ).execute()
        
        downloaded_refs = {}
        
        for subfolder in subfolders_results.get('files', []):
            folder_name = subfolder['name']
            folder_id = subfolder['id']
            print(f"📂 Processando pasta: {folder_name}")
            
            # Baixar shapefiles da subpasta
            shapefile_downloaded = self.download_shapefiles_from_folder(
                folder_id, folder_name, spatial_mapping, downloaded_refs
            )
            
        print(f"📋 Referências espaciais baixadas: {list(downloaded_refs.keys())}")
        return downloaded_refs
        
    def download_shapefiles_from_folder(self, folder_id, folder_name, spatial_mapping, downloaded_refs):
        """Baixa shapefiles de uma pasta específica"""
        # Buscar arquivos .shp
        shp_query = f"'{folder_id}' in parents and name contains '.shp' and trashed=false"
        shp_results = self.drive_service.files().list(
            q=shp_query,
            fields="files(id, name)"
        ).execute()
        
        for shp_file in shp_results.get('files', []):
            file_name = shp_file['name']
            base_name = file_name.replace('.shp', '')
            
            # Determinar tipo de referência
            ref_type = self.identify_reference_type(base_name, folder_name, spatial_mapping)
            
            if ref_type and ref_type not in downloaded_refs:
                # Criar pasta local
                local_folder = os.path.join(self.temp_dir, 'spatial_ref', ref_type)
                os.makedirs(local_folder, exist_ok=True)
                
                # Baixar shapefile completo
                success = self.download_complete_shapefile(shp_file['id'], local_folder, base_name, folder_id)
                
                if success:
                    shp_path = os.path.join(local_folder, f"{base_name}.shp")
                    downloaded_refs[ref_type] = shp_path
                    print(f"   ✅ {ref_type}: {file_name}")
                    
        return True
        
    def identify_reference_type(self, base_name, folder_name, spatial_mapping):
        """Identifica o tipo de referência espacial"""
        combined_name = f"{folder_name} {base_name}".lower()
        
        for ref_type, possible_names in spatial_mapping.items():
            for name in possible_names:
                if name.lower() in combined_name:
                    return ref_type
        return None
        
    def download_complete_shapefile(self, shp_file_id, local_folder, base_name, parent_folder_id):
        """Baixa todos os arquivos do shapefile (.shp, .shx, .dbf, .prj, etc.)"""
        try:
            extensions = ['.shp', '.shx', '.dbf', '.prj', '.cpg', '.sbn', '.sbx']
            essential_extensions = ['.shp', '.shx', '.dbf']
            downloaded_essential = 0
            
            for ext in extensions:
                query = f"'{parent_folder_id}' in parents and name contains '{base_name}{ext}' and trashed=false"
                results = self.drive_service.files().list(q=query, fields="files(id, name)").execute()
                
                for file_info in results.get('files', []):
                    local_path = os.path.join(local_folder, file_info['name'])
                    try:
                        self.download_file(file_info['id'], local_path)
                        if ext in essential_extensions:
                            downloaded_essential += 1
                    except Exception as e:
                        if ext in essential_extensions:
                            print(f"      ❌ Erro em arquivo essencial {file_info['name']}: {e}")
                            return False
            
            return downloaded_essential >= 3  # Pelo menos .shp, .shx, .dbf
            
        except Exception as e:
            print(f"      ❌ Erro ao baixar shapefile {base_name}: {e}")
            return False
            
    def apply_spatial_joins(self, gdf_focos, spatial_refs):
        """Aplica joins espaciais OBRIGATÓRIOS conforme script original"""
        print("🔗 APLICANDO JOINS ESPACIAIS...")
        
        crs_alvo = "EPSG:4326"
        gdf_result = gdf_focos.copy()
        initial_columns = set(gdf_result.columns)
        
        # Configurar mapeamento de colunas conforme script original
        column_mapping = {
            "uf": "NM_UF",
            "municipios": "NM_MUN", 
            "biomas": "Bioma",
            "terras_indigenas": "terrai_nom",
            "uso_solo": ["Cober_2023", "Classe_202"],
            "zee": "Nome_Atual"
        }
        
        # Carregar e aplicar cada referência espacial
        joins_aplicados = 0
        for chave in ['uf', 'municipios', 'biomas', 'terras_indigenas', 'uso_solo', 'zee']:
            if chave in spatial_refs:
                caminho = spatial_refs[chave]
                print(f"   🔗 Processando: {chave}")
                
                try:
                    # Carregar shapefile
                    try:
                        gdf_ref = gpd.read_file(caminho, encoding='utf-8')
                    except UnicodeDecodeError:
                        gdf_ref = gpd.read_file(caminho, encoding='latin1')
                    
                    print(f"      📊 Carregado: {len(gdf_ref)} geometrias")
                    
                    # Ajustar CRS
                    if gdf_ref.crs is not None and gdf_ref.crs != crs_alvo:
                        gdf_ref = gdf_ref.to_crs(crs_alvo)
                    
                    # Selecionar colunas relevantes
                    columns_to_keep = ["geometry"]
                    expected_columns = column_mapping.get(chave, [])
                    if isinstance(expected_columns, str):
                        expected_columns = [expected_columns]
                    
                    for col in expected_columns:
                        if col in gdf_ref.columns:
                            columns_to_keep.append(col)
                    
                    gdf_ref = gdf_ref[columns_to_keep]
                    
                    # Limpar índices anteriores
                    if "index_right" in gdf_result.columns:
                        gdf_result.drop(columns=["index_right"], inplace=True)
                    
                    # Aplicar join espacial
                    antes_join = len(gdf_result.columns)
                    gdf_result = gdf_result.sjoin(gdf_ref, how="left", predicate="within")
                    depois_join = len(gdf_result.columns)
                    
                    novas_colunas = depois_join - antes_join
                    if novas_colunas > 0:
                        joins_aplicados += 1
                        print(f"      ✅ Join aplicado: +{novas_colunas} colunas")
                    else:
                        print(f"      ⚠️ Join não adicionou colunas")
                        
                except Exception as e:
                    print(f"      ❌ Erro no join {chave}: {e}")
        
        # Limpeza final
        if "index_right" in gdf_result.columns:
            gdf_result.drop(columns=["index_right"], inplace=True)
            
        final_columns = set(gdf_result.columns)
        new_columns = final_columns - initial_columns
        
        print(f"✅ JOINS CONCLUÍDOS:")
        print(f"   📊 Joins aplicados: {joins_aplicados}")
        print(f"   📋 Novas colunas: {len(new_columns)}")
        if new_columns:
            print(f"   📝 Colunas adicionadas: {list(new_columns)}")
            
        return gdf_result
        
    def export_results(self, gdf_final, results_folder_id):
        """Exporta resultado com estratégia híbrida: arquivo principal + backup"""
        print("💾 EXPORTANDO RESULTADOS - ESTRATÉGIA HÍBRIDA...")
        
        try:
            # Salvar dados processados para uso posterior
            self.dados_processados = gdf_final
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            # ARQUIVO PRINCIPAL (fixo para o site)
            main_excel_name = "focos_qualificados_atual.xlsx"
            main_shp_name = "focos_qualificados_atual"
            
            # ARQUIVO BACKUP (com timestamp)
            backup_excel_name = f"backup_focos_qualificados_{timestamp}.xlsx"
            backup_shp_name = f"backup_focos_qualificados_{timestamp}"
            
            excel_path = os.path.join(self.temp_dir, main_excel_name)
            shp_path = os.path.join(self.temp_dir, f"{main_shp_name}.shp")
            
            # Preparar dados
            df_final = gdf_final.drop(columns="geometry")
            
            print(f"📊 Exportando: {len(df_final)} registros, {len(df_final.columns)} colunas")
            print(f"📋 Colunas: {list(df_final.columns)}")
            
            # Criar arquivos locais
            df_final.to_excel(excel_path, index=False)
            gdf_final.to_file(shp_path, driver="ESRI Shapefile")
            
            if results_folder_id:
                # 1. ATUALIZAR ARQUIVO PRINCIPAL (para o site)
                print("📤 Atualizando arquivo principal para o site...")
                main_file_id = self.update_main_file(excel_path, results_folder_id, main_excel_name)
                
                # 2. CRIAR BACKUP COM TIMESTAMP
                print("💾 Criando backup histórico...")
                self.upload_to_drive(excel_path, results_folder_id, backup_excel_name)
                self.upload_shapefile_complete(shp_path, results_folder_id, backup_shp_name)
                
                # 3. LIMPAR BACKUPS ANTIGOS (manter apenas 5)
                self.cleanup_old_backups(results_folder_id)
                
                # 4. GERAR LINK PÚBLICO FIXO
                if main_file_id:
                    public_link = self.create_public_link(main_file_id)
                    self.save_public_link_for_website(main_file_id)
                
            print(f"🎉 PROCESSO CONCLUÍDO: {len(gdf_final)} registros processados")
            return True
            
        except Exception as e:
            print(f"❌ ERRO na exportação: {e}")
            return False

    def update_main_file(self, local_path, folder_id, filename):
        """Atualiza o arquivo principal (mesmo ID, conteúdo novo)"""
        try:
            # Buscar arquivo principal existente
            query = f"'{folder_id}' in parents and name='{filename}' and trashed=false"
            results = self.drive_service.files().list(q=query, fields="files(id, name)").execute()
            
            files = results.get('files', [])
            
            if files:
                # Atualizar arquivo existente
                file_id = files[0]['id']
                media = MediaFileUpload(local_path, resumable=True)
                updated_file = self.drive_service.files().update(
                    fileId=file_id, media_body=media
                ).execute()
                print(f"   ✅ Arquivo principal atualizado: {filename} (ID: {file_id})")
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
                return file_id
                
        except Exception as e:
            print(f"   ❌ Erro ao atualizar arquivo principal: {e}")
            return None

    def save_public_link_for_website(self, file_id):
        """NOVA FUNÇÃO: Salva o link público para o site React usar"""
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
                "total_records": len(self.dados_processados) if self.dados_processados is not None else 0,
                "description": "Dados de focos de calor do Maranhão processados automaticamente",
                "source": "INPE",
                "processor": "IMESC",
                "columns": list(self.dados_processados.columns) if self.dados_processados is not None else [],
                "processing_timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "geographic_bounds": {
                    "north": float(self.dados_processados['lat'].max()) if self.dados_processados is not None else None,
                    "south": float(self.dados_processados['lat'].min()) if self.dados_processados is not None else None,
                    "east": float(self.dados_processados['lon'].max()) if self.dados_processados is not None else None,
                    "west": float(self.dados_processados['lon'].min()) if self.dados_processados is not None else None
                }
            }
            
            # Criar diretório data se não existir
            os.makedirs('data', exist_ok=True)
            
            # Salvar link para o site React usar
            with open('data/current_data_link.json', 'w', encoding='utf-8') as f:
                json.dump(link_info, f, indent=2, ensure_ascii=False)
                
            print(f"✅ Link público salvo: {public_link}")
            print(f"📁 Arquivo disponível em: data/current_data_link.json")
            print(f"📊 Total de registros: {link_info['total_records']}")
            
            return public_link
            
        except Exception as e:
            print(f"❌ Erro ao salvar link público: {e}")
            return None
            
    def cleanup_old_backups(self, folder_id):
        """Remove backups antigos, mantendo apenas os 5 mais recentes"""
        try:
            query = f"'{folder_id}' in parents and name contains 'backup_focos_qualificados' and trashed=false"
            results = self.drive_service.files().list(
                q=query, 
                fields="files(id, name, createdTime)",
                orderBy="createdTime desc"
            ).execute()
            
            files = results.get('files', [])
            
            if len(files) > 5:
                files_to_delete = files[5:]  # Manter apenas os 5 mais recentes
                for file in files_to_delete:
                    try:
                        self.drive_service.files().delete(fileId=file['id']).execute()
                        print(f"   🗑️ Backup antigo removido: {file['name']}")
                    except:
                        pass
                        
        except Exception as e:
            print(f"   ⚠️ Erro ao limpar backups: {e}")
            
    def create_public_link(self, file_id):
        """Torna o arquivo público e retorna link direto"""
        try:
            # Tornar público
            self.drive_service.permissions().create(
                fileId=file_id,
                body={'role': 'reader', 'type': 'anyone'}
            ).execute()
            
            # Retornar link direto
            public_link = f"https://drive.google.com/uc?id={file_id}&export=download"
            print(f"   🌐 Link público gerado: {public_link}")
            return public_link
            
        except Exception as e:
            print(f"   ⚠️ Erro ao criar link público: {e}")
            return None
            
    def save_public_link(self, public_link):
        """Salva o link público em arquivo para o site usar (VERSÃO ANTIGA - mantida para compatibilidade)"""
        if public_link:
            try:
                link_info = {
                    "public_url": public_link,
                    "last_updated": datetime.now().isoformat(),
                    "description": "Link direto para o arquivo principal de focos de calor do Maranhão"
                }
                
                # Salvar no diretório temporário (será commitado pelo GitHub Actions)
                os.makedirs('data', exist_ok=True)
                with open('data/current_data_link.json', 'w') as f:
                    json.dump(link_info, f, indent=2)
                    
                print(f"   📝 Link salvo em: data/current_data_link.json")
                
            except Exception as e:
                print(f"   ⚠️ Erro ao salvar link: {e}")
                
    def upload_to_drive(self, local_path, folder_id, filename):
        """Upload simples para Drive"""
        try:
            file_metadata = {'name': filename, 'parents': [folder_id]}
            media = MediaFileUpload(local_path, resumable=True)
            file = self.drive_service.files().create(
                body=file_metadata, media_body=media, fields='id,name'
            ).execute()
            print(f"📤 Upload: {filename}")
        except Exception as e:
            print(f"❌ Erro upload {filename}: {e}")
            
    def upload_shapefile_complete(self, shp_path, folder_id, base_filename):
        """Upload de todos os arquivos do shapefile"""
        shp_dir = os.path.dirname(shp_path)
        base_name = os.path.basename(shp_path).replace('.shp', '')
        
        for file in os.listdir(shp_dir):
            if file.startswith(base_name):
                file_path = os.path.join(shp_dir, file)
                self.upload_to_drive(file_path, folder_id, file)
                
    def cleanup(self):
        """Remove arquivos temporários"""
        try:
            shutil.rmtree(self.temp_dir)
            print(f"🧹 Limpeza concluída")
        except Exception as e:
            print(f"⚠️ Erro na limpeza: {e}")

    def process_heat_focus_data(self):
        """PROCESSO PRINCIPAL - GARANTIR PROCESSAMENTO COMPLETO"""
        print("🔥 INICIANDO PROCESSAMENTO COMPLETO DE FOCOS DE CALOR")
        print("🎯 OBJETIVO: Processar TODOS os dados + Aplicar joins espaciais")
        
        try:
            # 1. Encontrar pastas
            folders = self.find_folder_by_path("")
            focos_folder_id = folders.get("1. Focos")
            ref_folder_id = folders.get("2. Referências Espaciais") 
            results_folder_id = folders.get("3. Resultados")
            
            if not focos_folder_id:
                print("❌ ERRO CRÍTICO: Pasta de focos não encontrada!")
                return False
                
            # 2. Baixar TODOS os arquivos CSV
            csv_files = self.download_all_csv_files(focos_folder_id)
            if not csv_files:
                print("❌ ERRO CRÍTICO: Nenhum arquivo CSV baixado!")
                return False
                
            # 3. Carregar e concatenar TODOS os dados
            df_focos = self.load_and_concat_all_data(csv_files)
            if df_focos is None:
                print("❌ ERRO CRÍTICO: Nenhum dado válido carregado!")
                return False
                
            # 4. Criar GeoDataFrame
            gdf_focos = self.clean_and_prepare_geodataframe(df_focos)
            if gdf_focos is None:
                print("❌ ERRO CRÍTICO: Falha ao criar GeoDataFrame!")
                return False
                
            # 5. Processar referências espaciais (OBRIGATÓRIO)
            if ref_folder_id:
                print("📍 BAIXANDO REFERÊNCIAS ESPACIAIS...")
                spatial_refs = self.download_spatial_references(ref_folder_id)
                if spatial_refs:
                    print("🔗 APLICANDO JOINS ESPACIAIS...")
                    gdf_final = self.apply_spatial_joins(gdf_focos, spatial_refs)
                else:
                    print("⚠️ NENHUMA referência espacial baixada - usando dados básicos")
                    gdf_final = gdf_focos
            else:
                print("⚠️ Pasta de referências não encontrada - usando dados básicos")
                gdf_final = gdf_focos
                
            # 6. Exportar resultados
            success = self.export_results(gdf_final, results_folder_id)
            return success
            
        except Exception as e:
            print(f"❌ ERRO CRÍTICO no processamento: {e}")
            return False

def main():
    """Função principal"""
    processor = None
    try:
        print("🚀 INICIANDO PROCESSAMENTO AUTOMATIZADO - VERSÃO COMPLETA")
        print(f"🕐 Timestamp: {datetime.now().isoformat()}")
        
        processor = FocosCalorProcessor()
        success = processor.process_heat_focus_data()
        
        if success:
            print("🎉 PROCESSAMENTO CONCLUÍDO COM SUCESSO!")
            print("📊 Arquivo focos_qualificados_atual.xlsx atualizado")
            print("🔗 Link público disponível em data/current_data_link.json")
            print("🌐 Frontend React pode acessar os dados")
        else:
            print("❌ PROCESSAMENTO FALHOU!")
            
    except Exception as e:
        print(f"❌ ERRO FATAL: {e}")
        raise
        
    finally:
        if processor:
            processor.cleanup()

if __name__ == "__main__":
    main()
