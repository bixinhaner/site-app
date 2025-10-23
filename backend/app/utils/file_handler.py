import os
import uuid
import hashlib
from typing import Dict, Any, Optional
from fastapi import UploadFile
from PIL import Image, ImageDraw, ImageFont
import aiofiles

async def save_uploaded_file(
    file: UploadFile, 
    category: str, 
    sub_folder: str = None
) -> str:
    """保存上传的文件"""
    
    # 生成唯一文件名
    file_extension = os.path.splitext(file.filename)[1]
    unique_filename = f"{uuid.uuid4()}{file_extension}"
    
    # 构建文件路径
    base_dir = "uploads"
    if sub_folder:
        file_dir = os.path.join(base_dir, category, sub_folder)
    else:
        file_dir = os.path.join(base_dir, category)
    
    # 确保目录存在
    os.makedirs(file_dir, exist_ok=True)
    
    file_path = os.path.join(file_dir, unique_filename)
    
    # 异步保存文件
    async with aiofiles.open(file_path, 'wb') as f:
        content = await file.read()
        await f.write(content)
    
    return file_path

async def generate_watermark(
    image_path: str, 
    watermark_data: Dict[str, Any]
) -> str:
    """为图片添加水印"""
    
    try:
        # 打开原始图片
        with Image.open(image_path) as img:
            # 创建绘图对象
            draw = ImageDraw.Draw(img)
            
            # 设置字体（如果没有字体文件，使用默认字体）
            try:
                font = ImageFont.truetype("arial.ttf", 36)
            except:
                font = ImageFont.load_default()
            
            # 准备水印文本
            watermark_lines = []
            if "gps_coordinates" in watermark_data:
                watermark_lines.append(f"📍 GPS: {watermark_data['gps_coordinates']}")
            if "timestamp" in watermark_data:
                watermark_lines.append(f"🕐 Time: {watermark_data['timestamp']}")
            if "inspector" in watermark_data:
                watermark_lines.append(f"👤 Inspector: {watermark_data['inspector']}")
            if "accuracy" in watermark_data:
                watermark_lines.append(f"📊 Accuracy: {watermark_data['accuracy']}")
            
            # 计算水印位置和大小
            img_width, img_height = img.size
            watermark_text = "\n".join(watermark_lines)
            
            # 获取文本边界框
            bbox = draw.textbbox((0, 0), watermark_text, font=font)
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]
            
            # 设置水印位置（左下角）
            margin = 20
            x = margin
            y = img_height - text_height - margin
            
            # 绘制半透明背景
            background_padding = 10
            background_coords = [
                x - background_padding,
                y - background_padding,
                x + text_width + background_padding,
                y + text_height + background_padding
            ]
            
            # 创建一个临时图像用于背景
            overlay = Image.new('RGBA', img.size, (255, 255, 255, 0))
            overlay_draw = ImageDraw.Draw(overlay)
            
            # 绘制半透明背景
            overlay_draw.rectangle(background_coords, fill=(0, 0, 0, 180))
            
            # 将背景与原图合成
            img = Image.alpha_composite(img.convert('RGBA'), overlay).convert('RGB')
            draw = ImageDraw.Draw(img)
            
            # 绘制白色文字
            draw.multiline_text((x, y), watermark_text, font=font, fill=(255, 255, 255))
            
            # 生成新文件名
            base_name = os.path.splitext(image_path)[0]
            watermarked_path = f"{base_name}_watermarked.jpg"
            
            # 保存带水印的图片
            img.save(watermarked_path, "JPEG", quality=90)
            
            return watermarked_path
            
    except Exception as e:
        print(f"添加水印失败: {str(e)}")
        # 如果添加水印失败，返回原图路径
        return image_path

def calculate_file_hash(file_path: str) -> str:
    """计算文件MD5哈希值"""
    hash_md5 = hashlib.md5()
    
    try:
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()
    except Exception as e:
        print(f"计算文件哈希失败: {str(e)}")
        return ""

def validate_image_file(file: UploadFile) -> bool:
    """验证图片文件"""
    
    # 检查文件类型
    allowed_types = ["image/jpeg", "image/jpg", "image/png"]
    if file.content_type not in allowed_types:
        return False
    
    # 检查文件大小 (最大10MB)
    max_size = 10 * 1024 * 1024  # 10MB
    if hasattr(file, 'size') and file.size > max_size:
        return False
    
    return True

async def compress_image(
    image_path: str, 
    max_width: int = 1920, 
    max_height: int = 1080,
    quality: int = 85
) -> str:
    """压缩图片"""
    
    try:
        with Image.open(image_path) as img:
            # 获取原始尺寸
            original_width, original_height = img.size
            
            # 计算新尺寸，保持宽高比
            ratio = min(max_width / original_width, max_height / original_height)
            
            if ratio < 1:
                new_width = int(original_width * ratio)
                new_height = int(original_height * ratio)
                
                # 调整图片尺寸
                img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
            
            # 生成压缩文件路径
            base_name = os.path.splitext(image_path)[0]
            compressed_path = f"{base_name}_compressed.jpg"
            
            # 保存压缩后的图片
            img.convert('RGB').save(compressed_path, "JPEG", quality=quality, optimize=True)
            
            return compressed_path
            
    except Exception as e:
        print(f"压缩图片失败: {str(e)}")
        return image_path

def cleanup_temp_files(*file_paths):
    """清理临时文件"""
    for file_path in file_paths:
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
        except Exception as e:
            print(f"清理文件失败 {file_path}: {str(e)}")

def get_image_info(image_path: str) -> Dict[str, Any]:
    """获取图片信息"""
    
    try:
        with Image.open(image_path) as img:
            return {
                "width": img.width,
                "height": img.height,
                "format": img.format,
                "mode": img.mode,
                "size": os.path.getsize(image_path)
            }
    except Exception as e:
        return {"error": str(e)}

def extract_exif(image_path: str) -> Dict[str, Any]:
    """提取图片的EXIF元数据，包含GPS与时间信息（若有）。"""
    info: Dict[str, Any] = {}
    try:
        with Image.open(image_path) as img:
            exif = getattr(img, '_getexif', None)
            if not exif:
                return info
            raw = img.getexif()
            if not raw:
                return info
            # 将PIL的EXIF字典转换为可序列化的简单字典
            for tag_id, value in raw.items():
                try:
                    tag = Image.ExifTags.TAGS.get(tag_id, str(tag_id))
                except Exception:
                    tag = str(tag_id)
                try:
                    if isinstance(value, bytes):
                        continue
                    info[tag] = value
                except Exception:
                    continue
    except Exception:
        return {}
    return info

def add_text_watermark_inline(image_path: str, text: str, quality: int = 85) -> Optional[str]:
    """为图片右下角添加简单文字水印并覆盖保存，返回新路径。失败返回None。"""
    try:
        with Image.open(image_path) as img:
            img = img.convert('RGBA')
            draw = ImageDraw.Draw(img)
            try:
                font = ImageFont.truetype("arial.ttf", 24)
            except Exception:
                font = ImageFont.load_default()
            bbox = draw.textbbox((0,0), text, font=font)
            tw, th = bbox[2]-bbox[0], bbox[3]-bbox[1]
            margin = 10
            x = img.width - tw - margin
            y = img.height - th - margin
            # 半透明黑底
            overlay = Image.new('RGBA', img.size, (255,255,255,0))
            od = ImageDraw.Draw(overlay)
            od.rectangle([x-6, y-4, x+tw+6, y+th+4], fill=(0,0,0,140))
            combined = Image.alpha_composite(img, overlay)
            draw = ImageDraw.Draw(combined)
            draw.text((x,y), text, font=font, fill=(255,255,255,255))
            out_path = image_path
            combined.convert('RGB').save(out_path, 'JPEG', quality=quality, optimize=True)
            return out_path
    except Exception:
        return None
