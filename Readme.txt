-- About DreamSearch -- 

This program simulates a search engine and generates results and webpages.

Based on https://github.com/Sebby37/Dead-Internet

-- DreamSearch - Setup Guide --

1. Install LM Studio (or any other OpenAI-compatible backend) from https://lmstudio.ai/download?os=win32&arch=x86

2. In LM Studio, go to the Discover tab to download and install models. "Instruct" models are recommended but feel free to experiment with others.

-- Recommended Models by VRAM (Outdated) --
4gb - Qwen2.5 Coder 3B (Models less than 4B parameters are recommended)
8gb - Qwen2.5 Coder 7B (Models less than 9B parameters are recommended)
12gb - Meta Llama 3.1 8B (Models less than 10B parameters are recommended)
16gb - Qwen2.5 14B or Qwen2.5 Coder 14B (Models less than 14B parameters are recommended)

More model info is available at: https://llm.extractum.io/

3. Open the Developer tab in LM Studio.

4. Select your model at the top. Setting context length between 6000-8000 is recommended. Start the server if it does not start on it's own.

5. Leave LM Studio running in the background.

6. Install Python (ensure that it is added to your System PATH) - https://www.python.org/downloads/windows/

7. Download and extract the ZIP file provided.

8. Open a Command Prompt in the directory with the extracted files.

9. Run "pip install -r requirements.txt".

10. Run "main.py".

11. Navigate to http://127.0.0.1:5000

- Usage -

1. Open LM Studio.

2. Go to the Developer tab.

3. Select your model and start the server.

4. Open main.py

5. Navigate to http://127.0.0.1:5000