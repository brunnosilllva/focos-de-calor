#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Processamento automatizado de focos de calor do Maranhão
Adaptado do script original do Google Colab para GitHub Actions
"""

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
        """Encontra uma pasta pelo caminho relativo"""
        print("🔍 Buscando pastas no Google Drive...")
        
        # Para simplificar, vamos procurar pelas pastas principais
        folders_map = {
            "1. Focos": None,
            "2. Referências Espaciais": None,
            "3. Resultados": None
        }
        
        # Buscar todas as pastas compartilhadas
        results = self.drive_service.files().list(
            q="mimeType='application/vnd.google-apps.folder' and sharedWithMe=true",
            fields="files(id, name, parents)"
        ).execute()
        
        print(f"📁 Encontradas {len(results.get('files', []))} pastas compartilhadas:")
        for folder in results.get('files', []):
            print(f"   - {folder['name']} (ID: {folder['id']})")
            
        # Também buscar pastas que a service account pode acessar (não apenas compartilhadas)
        all_results = self.drive_service.files().list(
            q="mimeType='application/vnd.google-apps.folder'",
            fields="files(id, name, parents)"
        ).execute()
        
        print(f"📂 Total de pastas acessíveis: {len(all_results.get('files', []))}")
        
        # Procurar por nome exato e parcial
        for folder in all_results.get('files', []):
            folder_name = folder['name']
            print(f"   Verificando: '{folder_name}'")
            
            # Verificação exata
            if folder_name in folders_map:
                folders_map[folder_name] = folder['id']
                print(f"✅ Pasta encontrada (exata): {folder_name}")
            
            # Verificação parcial para nomes similares
            elif "Focos" in folder_name or "focos" in folder_name:
                folders_map["1. Focos"] = folder['id']
                print(f"✅ Pasta de focos encontrada (similar): {folder_name}")
            elif "Referências" in folder_name or "referencias" in folder_name:
                folders_map["2. Referências Espaciais"] = folder['id']
                print(f"✅ Pasta de referências encontrada (similar): {folder_name}")
            elif "Resultados" in folder_name or "resultados" in folder_name:
                folders_map["3. Resultados"] = folder['id']
                print(f"✅ Pasta de resultados encontrada (similar): {folder_name}")
                
        print(f"📋 Mapeamento final: {folders_map}")
        return folders_map
        
    def download_files_from_folder(self, folder_id, file_extension='.csv'):
        """Baixa todos os arquivos de uma pasta específica"""
        query = f"'{folder_id}' in parents and name contains '{file_extension}' and trashed=false"
        results = self.drive_service.files().list(
            q=query,
            fields="files(id, name, size)"
        ).execute()
        
        files = results.get('files', [])
        downloaded_files = []
        
        for file_info in files:
            if int(file_info.get('size', 0)) > 0:  # Apenas arquivos não vazios
                local_path = os.path.join(self.temp_dir, file_info['name'])
                self.download_file(file_info['id'], local_path)
                downloaded_files.append(local_path)
                print(f"📥 Baixado: {file_info['name']}")
                
        return downloaded_files
        
    def download_file(self, file_id, local_path):
        """Baixa um arquivo específico do Google Drive"""
        request = self.drive_service.files().get_media(fileId=file_id)
        with open(local_path, 'wb') as f:
            downloader = MediaIoBaseDownload(f, request)
            done = False
            while done is False:
                status, done = downloader.next_chunk()
                
    def download_spatial_references(self, ref_folder_id):
        """Baixa os arquivos de referência espacial"""
        # Estrutura dos arquivos espaciais conforme script original
        spatial_files = {
            "uf": "Unidades da Federação.shp",
            "municipios": "Municipios_2023.shp", 
            "biomas": "lm_bioma_250.shp",
            "terras_indigenas": "Terras Indigenas.shp",
            "uso_solo": "MA_2023_DISSOLVE_REPROJETADO.shp",
            "zee": "Zonas_atualizada_MA.shp"
        }
        
        # Buscar todos os arquivos .shp na pasta de referências
        query = f"'{ref_folder_id}' in parents and name contains '.shp' and trashed=false"
        results = self.drive_service.files().list(
            q=query,
            fields="files(id, name, parents)"
        ).execute()
        
        downloaded_refs = {}
        
        # Baixar arquivos encontrados
        for file_info in results.get('files', []):
            file_name = file_info['name']
            
            # Criar pasta local para o arquivo
            base_name = file_name.replace('.shp', '')
            local_folder = os.path.join(self.temp_dir, 'spatial_ref', base_name)
            os.makedirs(local_folder, exist_ok=True)
            
            # Baixar todos os arquivos relacionados (.shp, .shx, .dbf, .prj, etc.)
            self.download_shapefile_complete(file_info['id'], local_folder, base_name)
            
            # Mapear para a estrutura esperada
            shp_path = os.path.join(local_folder, f"{base_name}.shp")
            if os.path.exists(shp_path):
                for key, expected_name in spatial_files.items():
                    if expected_name.replace('.shp', '') in base_name:
                        downloaded_refs[key] = shp_path
                        print(f"📍 Referência espacial mapeada: {key} -> {base_name}")
                        break
                        
        return downloaded_refs
        
    def download_shapefile_complete(self, shp_file_id, local_folder, base_name):
        """Baixa todos os arquivos relacionados a um shapefile"""
        # Encontrar pasta pai do arquivo .shp
        shp_file = self.drive_service.files().get(fileId=shp_file_id, fields="parents").execute()
        parent_folder = shp_file['parents'][0]
        
        # Buscar todos os arquivos relacionados
        extensions = ['.shp', '.shx', '.dbf', '.prj', '.cpg', '.sbn', '.sbx']
        
        for ext in extensions:
            query = f"'{parent_folder}' in parents and name contains '{base_name}{ext}' and trashed=false"
            results = self.drive_service.files().list(q=query, fields="files(id, name)").execute()
            
            for file_info in results.get('files', []):
                local_path = os.path.join(local_folder, file_info['name'])
                try:
                    self.download_file(file_info['id'], local_path)
                except Exception as e:
                    print(f"⚠️ Não foi possível baixar {file_info['name']}: {e}")
                    
    def process_heat_focus_data(self):
        """Processo principal - replica a lógica do script original"""
        print("🔥 Iniciando processamento de focos de calor...")
        
        # 1. Encontrar pastas
        folders = self.find_folder_by_path("")
        focos_folder_id = folders.get("1. Focos")
        ref_folder_id = folders.get("2. Referências Espaciais") 
        results_folder_id = folders.get("3. Resultados")
        
        if not focos_folder_id:
            print("❌ Pasta de focos não encontrada no Drive")
            print("💡 Verifique se:")
            print("   1. As pastas estão compartilhadas com a service account")
            print("   2. O email da service account tem permissão de visualização")
            print("   3. Os nomes das pastas estão corretos")
            return False
            
        # 2. Baixar arquivos CSV de focos
        csv_files = self.download_files_from_folder(focos_folder_id, '.csv')
        
        if not csv_files:
            print("⚠️ Nenhum arquivo CSV encontrado na pasta de focos")
            return False
            
        # 3. Carregar e unificar dados de focos
        lista_df = []
        for csv_file in csv_files:
            try:
                df = pd.read_csv(csv_file)
                if not df.empty:
                    lista_df.append(df)
                    print(f"✅ Carregado: {os.path.basename(csv_file)} ({len(df)} registros)")
            except Exception as e:
                print(f"⚠️ Erro ao carregar {csv_file}: {e}")
                
        if not lista_df:
            print("❌ Nenhum dado válido encontrado nos arquivos CSV")
            return False
            
        # 4. Consolidar dados
        df_focos = pd.concat(lista_df, ignore_index=True)
        
        # Limpeza conforme script original
        if "Unnamed: 0" in df_focos.columns:
            df_focos.drop(columns=["Unnamed: 0"], inplace=True)
        if "M" in df_focos.columns:
            df_focos.rename(columns={"M": "lon"}, inplace=True)
            
        df_focos = df_focos.dropna(subset=["lat", "lon"])
        
        if df_focos.empty:
            print("❌ Nenhum dado válido após limpeza")
            return False
            
        # 5. Criar GeoDataFrame
        gdf_focos = gpd.GeoDataFrame(
            df_focos, 
            geometry=gpd.points_from_xy(df_focos["lon"], df_focos["lat"]), 
            crs="EPSG:4326"
        )
        
        print(f"🌍 GeoDataFrame criado com {len(gdf_focos)} pontos")
        
        # 6. Baixar e processar referências espaciais (se disponível)
        if ref_folder_id:
            spatial_refs = self.download_spatial_references(ref_folder_id)
            gdf_final = self.apply_spatial_joins(gdf_focos, spatial_refs)
        else:
            print("⚠️ Pasta de referências espaciais não encontrada, usando apenas dados básicos")
            gdf_final = gdf_focos
            
        # 7. Exportar resultados
        success = self.export_results(gdf_final, results_folder_id)
        
        return success
        
    def apply_spatial_joins(self, gdf_focos, spatial_refs):
        """Aplica os joins espaciais conforme script original"""
        print("🔗 Aplicando joins espaciais...")
        
        crs_alvo = "EPSG:4326"
        gdf_result = gdf_focos.copy()
        
        # Carregar dados espaciais
        dados_espaciais = {}
        for chave, caminho in spatial_refs.items():
            if os.path.exists(caminho):
                try:
                    gdf = gpd.read_file(caminho, encoding='utf-8')
                except UnicodeDecodeError:
                    gdf = gpd.read_file(caminho, encoding='latin1')
                    
                if gdf.crs is not None and gdf.crs != crs_alvo:
                    gdf = gdf.to_crs(crs_alvo)
                    
                dados_espaciais[chave] = gdf
                print(f"📍 Carregado: {chave}")
                
        # Aplicar joins espaciais (lógica do script original)
        for chave in ['uf', 'municipios', 'biomas', 'terras_indigenas', 'uso_solo', 'zee']:
            if chave in dados_espaciais:
                if "index_right" in gdf_result.columns:
                    gdf_result.drop(columns=["index_right"], inplace=True)
                    
                try:
                    gdf_result = gdf_result.sjoin(dados_espaciais[chave], how="left", predicate="within")
                    print(f"✅ Join espacial aplicado: {chave}")
                except Exception as e:
                    print(f"⚠️ Erro no join espacial {chave}: {e}")
                    
        if "index_right" in gdf_result.columns:
            gdf_result.drop(columns=["index_right"], inplace=True)
            
        return gdf_result
        
    def export_results(self, gdf_final, results_folder_id):
        """Exporta os resultados para Excel e Shapefile"""
        print("💾 Exportando resultados...")
        
        try:
            # Preparar arquivos de saída
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            excel_filename = f"focos_qualificados_{timestamp}.xlsx"
            shp_filename = f"focos_qualificados_{timestamp}.shp"
            
            excel_path = os.path.join(self.temp_dir, excel_filename)
            shp_path = os.path.join(self.temp_dir, shp_filename)
            
            # Exportar Excel
            df_final = gdf_final.drop(columns="geometry")
            df_final.to_excel(excel_path, index=False)
            print(f"📊 Excel criado: {excel_filename}")
            
            # Exportar Shapefile  
            gdf_final.to_file(shp_path, driver="ESRI Shapefile")
            print(f"🗺️ Shapefile criado: {shp_filename}")
            
            # Upload para Google Drive
            if results_folder_id:
                self.upload_file_to_drive(excel_path, results_folder_id, excel_filename)
                self.upload_shapefile_to_drive(shp_path, results_folder_id, shp_filename)
            else:
                print("⚠️ Pasta de resultados não encontrada, arquivos não foram enviados ao Drive")
                
            print(f"✅ Processo concluído! {len(gdf_final)} registros processados")
            return True
            
        except Exception as e:
            print(f"❌ Erro ao exportar resultados: {e}")
            return False
            
    def upload_file_to_drive(self, local_path, folder_id, filename):
        """Faz upload de um arquivo para o Google Drive"""
        try:
            file_metadata = {
                'name': filename,
                'parents': [folder_id]
            }
            
            media = MediaFileUpload(local_path, resumable=True)
            file = self.drive_service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id,name'
            ).execute()
            
            print(f"📤 Upload concluído: {filename} (ID: {file.get('id')})")
            
        except Exception as e:
            print(f"❌ Erro no upload de {filename}: {e}")
            
    def upload_shapefile_to_drive(self, shp_path, folder_id, base_filename):
        """Faz upload de todos os arquivos relacionados ao shapefile"""
        base_name = base_filename.replace('.shp', '')
        shp_dir = os.path.dirname(shp_path)
        
        # Encontrar todos os arquivos relacionados
        related_files = []
        for file in os.listdir(shp_dir):
            if file.startswith(base_name):
                related_files.append(os.path.join(shp_dir, file))
                
        # Upload de cada arquivo
        for file_path in related_files:
            filename = os.path.basename(file_path)
            self.upload_file_to_drive(file_path, folder_id, filename)
            
    def cleanup(self):
        """Remove arquivos temporários"""
        try:
            shutil.rmtree(self.temp_dir)
            print(f"🧹 Diretório temporário removido: {self.temp_dir}")
        except Exception as e:
            print(f"⚠️ Erro ao limpar arquivos temporários: {e}")

def main():
    """Função principal"""
    processor = None
    try:
        print("🚀 Iniciando processamento automatizado de focos de calor")
        print(f"🕐 Timestamp: {datetime.now().isoformat()}")
        
        processor = FocosCalorProcessor()
        success = processor.process_heat_focus_data()
        
        if success:
            print("🎉 Processamento concluído com sucesso!")
        else:
            print("⚠️ Processamento concluído com advertências")
            
    except Exception as e:
        print(f"❌ Erro no processamento: {e}")
        raise
        
    finally:
        if processor:
            processor.cleanup()

if __name__ == "__main__":
    main()
