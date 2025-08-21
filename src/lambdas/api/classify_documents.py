"""
Document Classification Lambda Handler
Accepts multiple files and classifies them using Gemini AI
"""

import json
import base64
import os
from typing import Dict, Any, List
import logging
import google.generativeai as genai
import boto3
from datetime import datetime
import uuid

# Setup logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Document types for classification
DOCUMENT_TYPES = [
    "Loss Run",
    "ACORD form", 
    "Supplemental forms",
    "Mod sheet"
]

class DocumentClassifier:
    def __init__(self):
        # Initialize Gemini
        api_key = os.environ.get('GEMINI_API_KEY')
        if not api_key:
            raise ValueError("GEMINI_API_KEY environment variable is required")
        
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel('gemini-pro')
        
        # Initialize S3
        self.s3_client = boto3.client('s3')
        self.bucket_name = os.environ.get('S3_BUCKET')
        if not self.bucket_name:
            raise ValueError("S3_BUCKET environment variable is required")
    
    def upload_file_to_s3(self, file_content: bytes, filename: str) -> str:
        """
        Upload file to S3 and return the S3 key
        """
        try:
            # Create unique S3 key with timestamp and UUID
            timestamp = datetime.now().strftime('%Y/%m/%d/%H-%M-%S')
            unique_id = str(uuid.uuid4())[:8]
            s3_key = f"documents/{timestamp}/{unique_id}_{filename}"
            
            # Upload to S3
            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=s3_key,
                Body=file_content,
                ContentType=self._get_content_type(filename)
            )
            
            logger.info(f"File uploaded to S3: s3://{self.bucket_name}/{s3_key}")
            return s3_key
            
        except Exception as e:
            logger.error(f"Error uploading {filename} to S3: {str(e)}")
            raise
    
    def _get_content_type(self, filename: str) -> str:
        """
        Determine content type based on file extension
        """
        extension = filename.lower().split('.')[-1] if '.' in filename else ''
        content_types = {
            'pdf': 'application/pdf',
            'xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            'xls': 'application/vnd.ms-excel',
            'csv': 'text/csv',
            'doc': 'application/msword',
            'docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
        }
        return content_types.get(extension, 'application/octet-stream')
    
    def classify_document_from_s3(self, s3_key: str, filename: str) -> Dict[str, Any]:
        """
        Classify a document stored in S3 using Gemini
        """
        try:
            # Download file from S3
            response = self.s3_client.get_object(Bucket=self.bucket_name, Key=s3_key)
            file_content = response['Body'].read()
            
            # Create the classification prompt
            prompt = self._build_classification_prompt(filename)
            
            # Generate content with file
            response = self.model.generate_content([prompt, file_content])
            
            # Parse the response
            classification_result = self._parse_classification_response(response.text, filename)
            
            # Add S3 information to result
            classification_result['s3_key'] = s3_key
            classification_result['s3_url'] = f"s3://{self.bucket_name}/{s3_key}"
            
            return classification_result
            
        except Exception as e:
            logger.error(f"Error classifying document {filename} from S3: {str(e)}")
            return {
                "filename": filename,
                "classification": "Unknown",
                "confidence": 0.0,
                "error": str(e),
                "s3_key": s3_key
            }
    
    def classify_document(self, file_content: bytes, filename: str) -> Dict[str, Any]:
        """
        Classify a single document using Gemini (legacy method - now uses S3)
        """
        try:
            # First upload to S3
            s3_key = self.upload_file_to_s3(file_content, filename)
            
            # Then classify from S3
            return self.classify_document_from_s3(s3_key, filename)
            
        except Exception as e:
            logger.error(f"Error in classify_document for {filename}: {str(e)}")
            return {
                "filename": filename,
                "classification": "Unknown",
                "confidence": 0.0,
                "error": str(e)
            }
    
    def _build_classification_prompt(self, filename: str) -> str:
        """
        Build the prompt for document classification
        """
        prompt = f"""
        You are a document classification expert for insurance and risk management documents.
        
        Analyze the uploaded file and classify it into exactly one of these four categories:
        
        1. **Loss Run** - Documents containing loss history, claims data, or loss statistics
        2. **ACORD form** - Standard insurance forms (ACORD 25, ACORD 28, etc.)
        3. **Supplemental forms** - Additional forms, endorsements, or riders
        4. **Mod sheet** - Experience modification worksheets or rating documents
        
        Filename: {filename}
        
        Instructions:
        - Analyze the document content and filename
        - Classify it into exactly one of the four categories above
        
        Respond with only a JSON object in this exact format:
        {{
            "classification": "ONE_OF_THE_FOUR_TYPES",
        }}
        
        Do not include any other text, only the JSON object.
        """
        return prompt
    
    def _parse_classification_response(self, response_text: str, filename: str) -> Dict[str, Any]:
        """
        Parse the response from Gemini
        """
        try:
            # Clean the response text
            response_text = response_text.strip()
            
            # Find JSON object in response
            start_idx = response_text.find('{')
            end_idx = response_text.rfind('}') + 1
            
            if start_idx != -1 and end_idx != 0:
                json_str = response_text[start_idx:end_idx]
                result = json.loads(json_str)
            else:
                # Fallback parsing
                result = self._fallback_parsing(response_text)
            
            # Validate classification
            classification = result.get("classification", "").strip()
            if classification not in DOCUMENT_TYPES:
                logger.warning(f"Invalid classification for {filename}: {classification}")
                classification = "Unknown"
            
            return {
                "filename": filename,
                "classification": classification,
            }
            
        except Exception as e:
            logger.error(f"Error parsing classification response for {filename}: {str(e)}")
            return {
                "filename": filename,
                "classification": "Unknown",
            }
    
    def _fallback_parsing(self, response: str) -> Dict[str, Any]:
        """
        Fallback parsing if JSON parsing fails
        """
        response_lower = response.lower()
        
        # Simple keyword-based classification
        if any(word in response_lower for word in ["loss run", "loss", "claims", "history"]):
            classification = "Loss Run"
        elif any(word in response_lower for word in ["acord", "form"]):
            classification = "ACORD form"
        elif any(word in response_lower for word in ["supplemental", "endorsement", "rider"]):
            classification = "Supplemental forms"
        elif any(word in response_lower for word in ["mod", "modification", "rating"]):
            classification = "Mod sheet"
        else:
            classification = "Unknown"
        
        return {
            "classification": classification,
        }

def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Main Lambda handler for document classification
    """
    try:
        logger.info("Document classification request received")
        
        # For now, let's handle a simple JSON request with base64 encoded files
        # We'll improve the multipart parsing later
        
        body = json.loads(event.get('body', '{}'))
        files = body.get('files', [])
        
        if not files:
            return {
                'statusCode': 400,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({
                    'error': 'No files provided'
                })
            }
        
        logger.info(f"Processing {len(files)} files")
        
        # Initialize classifier
        classifier = DocumentClassifier()
        
        # Classify each file
        classifications = []
        for file_data in files:
            filename = file_data.get('filename', 'unknown')
            content_b64 = file_data.get('content', '')
            
            # Decode base64 content
            try:
                content = base64.b64decode(content_b64)
            except Exception as e:
                logger.error(f"Error decoding file {filename}: {str(e)}")
                classifications.append({
                    "filename": filename,
                    "classification": "Unknown",
                    "confidence": 0.0,
                    "error": "Invalid file content"
                })
                continue
            
            logger.info(f"Processing file: {filename}")
            result = classifier.classify_document(content, filename)
            classifications.append(result)
        
        # Return results
        response_data = {
            "total_files": len(files),
            "classifications": classifications
        }
        
        logger.info(f"Classification completed for {len(files)} files")
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'success': True,
                'data': response_data
            })
        }
        
    except Exception as e:
        logger.error(f"Unexpected error in document classification: {str(e)}")
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'error': f'Internal server error: {str(e)}'
            })
        } 