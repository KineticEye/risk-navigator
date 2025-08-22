"""
Document Classification Lambda Handler
Accepts multiple files and classifies them using Gemini AI
Supports API Gateway, S3 events, and S3 file selection
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
import io

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
        self.model = genai.GenerativeModel('gemini-2.5-flash')
        self.client = genai  # For file uploads
        
        # Initialize S3
        self.s3_client = boto3.client('s3')
        self.uploads_bucket = os.environ.get('UPLOADS_BUCKET')
        self.results_bucket = os.environ.get('RESULTS_BUCKET')
        
        # Legacy support for single bucket
        if not self.uploads_bucket:
            #Check parameter store for the bucket name
            self.uploads_bucket = os.environ.get('S3_BUCKET', 'risk-navigator-documents-dev')
        if not self.results_bucket:
            self.results_bucket = self.uploads_bucket
    
    def list_s3_files(self, prefix: str = '') -> List[Dict[str, Any]]:
        """
        List files in the S3 bucket for selection
        """
        try:
            response = self.s3_client.list_objects_v2(
                Bucket=self.uploads_bucket,
                Prefix=prefix,
                MaxKeys=100
            )
            
            files = []
            for obj in response.get('Contents', []):
                # Skip folders (keys ending with /)
                if not obj['Key'].endswith('/'):
                    files.append({
                        'key': obj['Key'],
                        'filename': obj['Key'].split('/')[-1],
                        'size': obj['Size'],
                        'last_modified': obj['LastModified'].isoformat(),
                        'full_path': f"s3://{self.uploads_bucket}/{obj['Key']}"
                    })
            
            return files
            
        except Exception as e:
            logger.error(f"Error listing S3 files: {str(e)}")
            return []
    
    def classify_existing_s3_file(self, s3_key: str) -> Dict[str, Any]:
        """
        Classify an existing file in S3 by its key
        """
        try:
            filename = s3_key.split('/')[-1]
            logger.info(f"Classifying existing S3 file: {self.uploads_bucket}/{s3_key}")
            
            # Download file from S3
            response = self.s3_client.get_object(Bucket=self.uploads_bucket, Key=s3_key)
            file_content = response['Body'].read()
            
            # Create the classification prompt
            prompt = self._build_classification_prompt(filename)
            
            # Determine how to handle the file based on type
            mime_type = self._get_content_type(filename)
            contents = self._prepare_gemini_content(file_content, filename, mime_type, prompt)
            
            # Generate content with Gemini
            gemini_response = self.model.generate_content(contents)
            
            # Parse the response
            classification_result = self._parse_classification_response(gemini_response.text, filename)
            
            # Add metadata
            classification_result.update({
                'source_bucket': self.uploads_bucket,
                'source_key': s3_key,
                'processed_at': datetime.utcnow().isoformat(),
                'file_size': len(file_content),
                'processing_method': 'existing_file_selection'
            })
            
            # Try to save results (will work if we have write permissions)
            try:
                result_key = self._save_classification_result(classification_result, filename)
                if result_key:
                    classification_result['result_key'] = result_key
            except Exception as e:
                logger.warning(f"Could not save result to S3: {str(e)}")
                classification_result['note'] = 'Result not saved to S3 due to permissions'
            
            logger.info(f"Classification completed for {filename}: {classification_result['classification']}")
            return classification_result
            
        except Exception as e:
            logger.error(f"Error classifying existing S3 file {s3_key}: {str(e)}")
            return {
                "filename": s3_key.split('/')[-1],
                "classification": "Unknown",
                "error": str(e),
                "source_bucket": self.uploads_bucket,
                "source_key": s3_key,
                "processed_at": datetime.utcnow().isoformat()
            }
    
    def classify_document_from_s3_event(self, bucket: str, key: str) -> Dict[str, Any]:
        """
        Classify a document from S3 event trigger
        """
        try:
            filename = key.split('/')[-1]  # Extract filename from S3 key
            logger.info(f"Processing S3 event for {bucket}/{key}")
            
            # Download file from S3
            response = self.s3_client.get_object(Bucket=bucket, Key=key)
            file_content = response['Body'].read()
            
            # Create the classification prompt
            prompt = self._build_classification_prompt(filename)
            
            # Determine how to handle the file based on type
            mime_type = self._get_content_type(filename)
            contents = self._prepare_gemini_content(file_content, filename, mime_type, prompt)
            
            # Generate content with Gemini
            gemini_response = self.model.generate_content(contents)
            
            # Parse the response
            classification_result = self._parse_classification_response(gemini_response.text, filename)
            
            # Add metadata
            classification_result.update({
                'source_bucket': bucket,
                'source_key': key,
                'processed_at': datetime.utcnow().isoformat(),
                'file_size': len(file_content)
            })
            
            # Save results to results bucket
            result_key = self._save_classification_result(classification_result, filename)
            classification_result['result_key'] = result_key
            
            logger.info(f"Classification completed for {filename}: {classification_result['classification']}")
            return classification_result
            
        except Exception as e:
            logger.error(f"Error processing S3 event for {bucket}/{key}: {str(e)}")
            error_result = {
                "filename": filename,
                "classification": "Unknown",
                "error": str(e),
                "source_bucket": bucket,
                "source_key": key,
                "processed_at": datetime.utcnow().isoformat()
            }
            # Still save error results
            self._save_classification_result(error_result, filename)
            return error_result
    
    def _save_classification_result(self, result: Dict[str, Any], filename: str) -> str:
        """
        Save classification result to S3 results bucket (if permissions allow)
        """
        try:
            # Create result key
            timestamp = datetime.now().strftime('%Y/%m/%d/%H-%M-%S')
            result_key = f"results/{timestamp}/{filename}.json"
            
            # Save to S3
            self.s3_client.put_object(
                Bucket=self.results_bucket,
                Key=result_key,
                Body=json.dumps(result, indent=2),
                ContentType='application/json'
            )
            
            logger.info(f"Classification result saved to s3://{self.results_bucket}/{result_key}")
            return result_key
            
        except Exception as e:
            logger.error(f"Error saving result for {filename}: {str(e)}")
            return None
    
    def upload_file_to_s3(self, file_content: bytes, filename: str) -> str:
        """
        Upload file to S3 and return the S3 key (for API Gateway usage)
        """
        try:
            # Create unique S3 key with timestamp and UUID
            timestamp = datetime.now().strftime('%Y/%m/%d/%H-%M-%S')
            unique_id = str(uuid.uuid4())[:8]
            s3_key = f"api-uploads/{timestamp}/{unique_id}_{filename}"
            
            # Upload to uploads bucket
            self.s3_client.put_object(
                Bucket=self.uploads_bucket,
                Key=s3_key,
                Body=file_content,
                ContentType=self._get_content_type(filename)
            )
            
            logger.info(f"File uploaded to S3: s3://{self.uploads_bucket}/{s3_key}")
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
        Classify a document stored in S3 using Gemini File API (for API Gateway)
        """
        try:
            # Download file from S3
            response = self.s3_client.get_object(Bucket=self.uploads_bucket, Key=s3_key)
            file_content = response['Body'].read()
            
            # Create the classification prompt
            prompt = self._build_classification_prompt(filename)
            
            # Determine how to handle the file based on type
            mime_type = self._get_content_type(filename)
            contents = self._prepare_gemini_content(file_content, filename, mime_type, prompt)
            
            # Generate content with Gemini
            gemini_response = self.model.generate_content(contents)
            
            # Parse the response
            classification_result = self._parse_classification_response(gemini_response.text, filename)
            
            # Add S3 information to result
            classification_result['s3_key'] = s3_key
            classification_result['s3_url'] = f"s3://{self.uploads_bucket}/{s3_key}"
            
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
    
    def _prepare_gemini_content(self, file_content: bytes, filename: str, mime_type: str, prompt: str) -> List:
        """
        Prepare content for Gemini based on file type (following reference pattern)
        """
        try:
            # Case 1: PDF — Upload to Gemini File API
            if mime_type == "application/pdf":
                logger.info(f"Uploading PDF {filename} to Gemini File API")
                uploaded_file = self.client.upload_file(
                    path=io.BytesIO(file_content),
                    display_name=filename,
                    mime_type="application/pdf"
                )
                contents = [uploaded_file, prompt]
                
            # Case 2: Excel — Convert to CSV text
            elif mime_type in [
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                "application/vnd.ms-excel"
            ]:
                logger.info(f"Converting Excel file {filename} to text")
                try:
                    import pandas as pd
                    df = pd.read_excel(io.BytesIO(file_content))
                    csv_text = df.to_csv(index=False)
                    contents = [
                        f"The following CSV data is from an uploaded Excel file named '{filename}':\n\n{csv_text}",
                        prompt
                    ]
                except ImportError:
                    logger.warning("pandas not available, treating Excel as binary")
                    # Fallback: treat as binary (less effective but works)
                    contents = [prompt, file_content]
                    
            # Case 3: CSV — Convert to text
            elif mime_type == "text/csv":
                logger.info(f"Processing CSV file {filename} as text")
                csv_text = file_content.decode('utf-8')
                contents = [
                    f"The following CSV data is from file '{filename}':\n\n{csv_text}",
                    prompt
                ]
                
            # Case 4: Text files — Send as text
            elif filename.lower().endswith(('.txt', '.doc')):
                logger.info(f"Processing text file {filename}")
                try:
                    text_content = file_content.decode('utf-8')
                    contents = [
                        f"The following text is from file '{filename}':\n\n{text_content}",
                        prompt
                    ]
                except UnicodeDecodeError:
                    # Fallback: treat as binary
                    logger.warning(f"Could not decode {filename} as text, treating as binary")
                    contents = [prompt, file_content]
                    
            # Case 5: Other files — Send as binary (fallback)
            else:
                logger.info(f"Processing {filename} as binary data")
                contents = [prompt, file_content]
            
            # Final safety check — ensure no file-like objects for non-PDF files
            if mime_type != "application/pdf":
                safe_contents = []
                for item in contents:
                    if hasattr(item, "read"):
                        logger.error(f"File-like object detected for non-PDF file {filename}")
                        raise ValueError("Only PDF files can be uploaded; all other types must be text")
                    safe_contents.append(item)
                contents = safe_contents
            
            return contents
            
        except Exception as e:
            logger.error(f"Error preparing content for {filename}: {str(e)}")
            # Emergency fallback
            return [prompt, f"Error processing file {filename}: {str(e)}"]
    
    def classify_document(self, file_content: bytes, filename: str) -> Dict[str, Any]:
        """
        Classify a single document using Gemini (now uses S3 + File API)
        """
        try:
            # First upload to S3
            s3_key = self.upload_file_to_s3(file_content, filename)
            
            # Then classify from S3 using Gemini File API
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

def s3_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    S3 Event Handler - processes files uploaded to S3
    """
    try:
        logger.info("S3 event received")
        logger.info(f"Event: {json.dumps(event)}")
        
        # Initialize classifier
        classifier = DocumentClassifier()
        
        # Process each S3 record
        results = []
        for record in event.get('Records', []):
            if record.get('eventSource') == 'aws:s3':
                bucket = record['s3']['bucket']['name']
                key = record['s3']['object']['key']
                
                # Process the file
                result = classifier.classify_document_from_s3_event(bucket, key)
                results.append(result)
        
        logger.info(f"Processed {len(results)} files from S3 event")
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'success': True,
                'processed_files': len(results),
                'results': results
            })
        }
        
    except Exception as e:
        logger.error(f"Error in S3 handler: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': f'S3 processing error: {str(e)}'
            })
        }

def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Main Lambda handler - routes between API Gateway and S3 events
    """
    try:
        # Check if this is an S3 event
        if 'Records' in event and event['Records']:
            first_record = event['Records'][0]
            if first_record.get('eventSource') == 'aws:s3':
                return s3_handler(event, context)
        
        # Parse API Gateway event
        logger.info("API Gateway event received")
        
        # Parse the request body
        body = json.loads(event.get('body', '{}'))
        
        # Initialize classifier
        classifier = DocumentClassifier()
        
        # Check the action type
        action = body.get('action', 'classify_files')
        
        if action == 'list_files':
            # List S3 files
            prefix = body.get('prefix', '')
            files = classifier.list_s3_files(prefix)
            
            return {
                'statusCode': 200,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({
                    'success': True,
                    'files': files,
                    'bucket': classifier.uploads_bucket
                })
            }
        
        elif action == 'classify_existing':
            # Classify existing S3 files
            s3_keys = body.get('s3_keys', [])
            
            if not s3_keys:
                return {
                    'statusCode': 400,
                    'headers': {
                        'Content-Type': 'application/json',
                        'Access-Control-Allow-Origin': '*'
                    },
                    'body': json.dumps({
                        'error': 'No S3 keys provided'
                    })
                }
            
            logger.info(f"Classifying {len(s3_keys)} existing files from S3")
            
            # Classify each existing file
            classifications = []
            for s3_key in s3_keys:
                logger.info(f"Processing existing S3 file: {s3_key}")
                result = classifier.classify_existing_s3_file(s3_key)
                classifications.append(result)
            
            return {
                'statusCode': 200,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({
                    'success': True,
                    'data': {
                        'total_files': len(s3_keys),
                        'classifications': classifications
                    }
                })
            }
        
        else:
            # Default: classify uploaded files (base64)
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
            
            logger.info(f"Processing {len(files)} files via API Gateway")
            
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
        logger.error(f"Unexpected error in Lambda handler: {str(e)}")
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