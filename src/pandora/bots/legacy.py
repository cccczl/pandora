# -*- coding: utf-8 -*-

import re
import uuid

import pyperclip
from rich.prompt import Prompt, Confirm

from .. import __version__
from ..openai.utils import Console


class ChatPrompt:
    def __init__(self, prompt: str = None, parent_id=None, message_id=None):
        self.prompt = prompt
        self.parent_id = parent_id or self.gen_message_id()
        self.message_id = message_id or self.gen_message_id()

    @staticmethod
    def gen_message_id():
        return str(uuid.uuid4())


class State:
    def __init__(self, title=None, conversation_id=None, model_slug=None, user_prompt=ChatPrompt(),
                 chatgpt_prompt=ChatPrompt()):
        self.title = title
        self.conversation_id = conversation_id
        self.model_slug = model_slug
        self.user_prompt = user_prompt
        self.chatgpt_prompt = chatgpt_prompt
        self.user_prompts = []
        self.edit_index = None


class ChatBot:
    def __init__(self, chatgpt):
        self.chatgpt = chatgpt
        self.token_key = None
        self.state = None

    def run(self):
        self.token_key = self.__choice_token_key()

        if conversation_base := self.__choice_conversation():
            self.__load_conversation(conversation_base['id'])
        else:
            self.__new_conversation()

        self.__talk_loop()

    def __talk_loop(self):
        while True:
            Console.info_b(
                f"You{' (edit)' if self.state and self.state.edit_index else ''}:"
            )

            prompt = self.__get_input()
            if not prompt:
                continue

            if prompt[0] == '/':
                self.__process_command(prompt)
                continue

            self.__talk(prompt)

    @staticmethod
    def __get_input():
        lines = []
        while True:
            line = input()

            if not line:
                break

            if line[0] == '/':
                return line

            lines.append(line)

        return '\n'.join(lines)

    def __process_command(self, command):
        command = command.strip().lower()

        if command in ['/quit', '/exit', '/bye']:
            raise KeyboardInterrupt
        elif command in ['/del', '/delete', '/remove']:
            self.__del_conversation(self.state)
        elif command in ['/title', '/set_title', '/set-title']:
            self.__set_conversation_title(self.state)
        elif command == '/select':
            self.run()
        elif command in ['/refresh', '/reload']:
            self.__load_conversation(self.state.conversation_id)
        elif command == '/new':
            self.__new_conversation()
            self.__talk_loop()
        elif command in ['/regen', '/regenerate']:
            self.__regenerate_reply(self.state)
        elif command in ['/goon', '/continue']:
            self.__continue(self.state)
        elif command in ['/edit', '/modify']:
            self.__edit_choice()
        elif command == '/token':
            self.__print_access_token()
        elif command in ['/cls', '/clear']:
            self.__clear_screen()
        elif command in ['/copy', '/cp']:
            self.__copy_text()
        elif command in ['/copy_code', "/cp_code"]:
            self.__copy_code()
        elif command in ['/ver', '/version']:
            self.__print_version()
        else:
            self.__print_usage()

    @staticmethod
    def __print_usage():
        Console.info_b('\n#### Command list:')
        print('/?\t\tShow this help message.')
        print('/title\t\tSet the current conversation\'s title.')
        print('/select\t\tChoice a different conversation.')
        print('/reload\t\tReload the current conversation.')
        print('/regen\t\tRegenerate response.')
        print('/continue\t\tContinue generating.')
        print('/edit\t\tEdit one of your previous prompt.')
        print('/new\t\tStart a new conversation.')
        print('/del\t\tDelete the current conversation.')
        print('/token\t\tPrint your access token.')
        print('/copy\t\tCopy the last response to clipboard.')
        print('/copy_code\t\tCopy code from last response.')
        print('/clear\t\tClear your screen.')
        print('/version\tPrint the version of Pandora.')
        print('/exit\t\tExit Pandora.')
        print()

    def __edit_choice(self):
        if not self.state.user_prompts:
            return

        choices = []
        pattern = re.compile(r'\s+')
        Console.info_b('Choice your prompt to edit:')
        for idx, item in enumerate(self.state.user_prompts):
            number = str(idx + 1)
            choices.append(number)

            preview_prompt = re.sub(pattern, ' ', item.prompt)
            if len(preview_prompt) > 40:
                preview_prompt = f'{preview_prompt[:40]}...'

            Console.info(f'  {number}.\t{preview_prompt}')

        choices.append('c')
        Console.warn('  c.\t** Cancel')

        default_choice = None if len(choices) > 2 else '1'
        while True:
            choice = Prompt.ask('Your choice', choices=choices, show_choices=False, default=default_choice)
            if choice == 'c':
                return

            self.state.edit_index = int(choice)
            return

    def __print_access_token(self):
        Console.warn_b('\n#### Your access token (keep it private)')
        Console.warn(self.chatgpt.get_access_token(token_key=self.token_key))
        print()

    def __clear_screen(self):
        Console.clear()

        if self.state:
            self.__print_conversation_title(self.state.title)

    @staticmethod
    def __print_version():
        Console.debug_bh(f'#### Version: {__version__}')
        print()

    def __new_conversation(self):
        self.state = State(model_slug=self.__choice_model()['slug'])

        self.state.title = 'New Chat'
        self.__print_conversation_title(self.state.title)

    @staticmethod
    def __print_conversation_title(title: str):
        Console.info_bh(f'==================== {title} ====================')
        Console.debug_h('Double enter to send. Type /? for help.')

    def __set_conversation_title(self, state: State):
        if not state.conversation_id:
            Console.error('#### Conversation has not been created.')
            return

        new_title = Prompt.ask('New title')
        if len(new_title) > 64:
            Console.error('#### Title too long.')
            return

        if self.chatgpt.set_conversation_title(state.conversation_id, new_title, token=self.token_key):
            state.title = new_title
            Console.debug('#### Set title success.')
        else:
            Console.error('#### Set title failed.')

    def __clear_conversations(self):
        if not Confirm.ask('Are you sure?', default=False):
            return

        if self.chatgpt.clear_conversations(token=self.token_key):
            self.run()
        else:
            Console.error('#### Clear conversations failed.')

    def __del_conversation(self, state: State):
        if not state.conversation_id:
            Console.error('#### Conversation has not been created.')
            return

        if not Confirm.ask('Are you sure?', default=False):
            return

        if self.chatgpt.del_conversation(state.conversation_id, token=self.token_key):
            self.run()
        else:
            Console.error('#### Delete conversation failed.')

    def __load_conversation(self, conversation_id):
        if not conversation_id:
            return

        self.state = State(conversation_id=conversation_id)

        nodes = []
        result = self.chatgpt.get_conversation(conversation_id, token=self.token_key)
        current_node_id = result['current_node']

        while True:
            node = result['mapping'][current_node_id]
            if not node.get('parent'):
                break

            nodes.insert(0, node)
            current_node_id = node['parent']

        self.state.title = result['title']
        self.__print_conversation_title(self.state.title)

        merge = False
        for node in nodes:
            message = node['message']
            if 'model_slug' in message['metadata']:
                self.state.model_slug = message['metadata']['model_slug']

            role = message['author']['role'] if 'author' in message else message['role']

            if role == 'user':
                prompt = self.state.user_prompt
                self.state.user_prompts.append(ChatPrompt(message['content']['parts'][0], parent_id=node['parent']))

                Console.info_b('You:')
                Console.info(message['content']['parts'][0])
            elif role == 'assistant':
                prompt = self.state.chatgpt_prompt

                if not merge:
                    Console.success_b('ChatGPT:')
                Console.success(message['content']['parts'][0])

                merge = 'end_turn' in message and message['end_turn'] is None
            else:
                continue

            prompt.prompt = message['content']['parts'][0]
            prompt.parent_id = node['parent']
            prompt.message_id = node['id']

            if not merge:
                print()

    def __talk(self, prompt):
        Console.success_b('ChatGPT:')

        first_prompt = not self.state.conversation_id

        if self.state.edit_index:
            idx = self.state.edit_index - 1
            user_prompt = self.state.user_prompts[idx]
            self.state.user_prompt = ChatPrompt(prompt, parent_id=user_prompt.parent_id)
            self.state.user_prompts = self.state.user_prompts[:idx]

            self.state.edit_index = None
        else:
            self.state.user_prompt = ChatPrompt(prompt, parent_id=self.state.chatgpt_prompt.message_id)

        status, _, generator = self.chatgpt.talk(prompt, self.state.model_slug, self.state.user_prompt.message_id,
                                                 self.state.user_prompt.parent_id, self.state.conversation_id,
                                                 token=self.token_key)
        self.__print_reply(status, generator)

        self.state.user_prompts.append(self.state.user_prompt)

        if first_prompt:
            new_title = self.chatgpt.gen_conversation_title(self.state.conversation_id, self.state.model_slug,
                                                            self.state.chatgpt_prompt.message_id, token=self.token_key)
            self.state.title = new_title
            Console.debug_bh(f'#### Title generated: {new_title}')

    def __regenerate_reply(self, state):
        if not state.conversation_id:
            Console.error('#### Conversation has not been created.')
            return

        status, _, generator = self.chatgpt.regenerate_reply(state.user_prompt.prompt, state.model_slug,
                                                             state.conversation_id, state.user_prompt.message_id,
                                                             state.user_prompt.parent_id, token=self.token_key)
        print()
        Console.success_b('ChatGPT:')
        self.__print_reply(status, generator)

    def __continue(self, state):
        if not state.conversation_id:
            Console.error('#### Conversation has not been created.')
            return

        status, _, generator = self.chatgpt.goon(state.model_slug, state.chatgpt_prompt.message_id,
                                                 state.conversation_id, token=self.token_key)
        print()
        Console.success_b('ChatGPT:')
        self.__print_reply(status, generator)

    def __print_reply(self, status, generator):
        if status != 200:
            raise Exception(status, next(generator))

        p = 0
        for result in generator:
            if result['error']:
                raise Exception(result['error'])

            if not result['message']:
                raise Exception('miss message property.')

            text = None
            message = result['message']
            if message['author']['role'] == 'assistant':
                text = message['content']['parts'][0][p:]
                p += len(text)

            self.state.conversation_id = result['conversation_id']
            self.state.chatgpt_prompt.prompt = message['content']['parts'][0]
            self.state.chatgpt_prompt.parent_id = self.state.user_prompt.message_id
            self.state.chatgpt_prompt.message_id = message['id']

            if message['author']['role'] == 'system':
                self.state.user_prompt.parent_id = message['id']

            if text:
                Console.success(text, end='')

        print('\n')

    def __choice_conversation(self, page=1, page_size=20):
        conversations = self.chatgpt.list_conversations((page - 1) * page_size, page_size, token=self.token_key)
        if not conversations['total']:
            return None

        choices = ['c', 'r', 'dd']
        items = conversations['items']
        first_page = conversations['offset'] == 0
        last_page = (conversations['offset'] + conversations['limit']) >= conversations['total']

        Console.info_b(f'Choice conversation (Page {page}):')
        for idx, item in enumerate(items):
            number = str(idx + 1)
            choices.extend((number, f't{number}', f'd{number}'))
            Console.info('  {}.\t{}'.format(number, item['title'].replace('\n', ' ')))

        if not last_page:
            choices.append('n')
            Console.warn('  n.\t>> Next page')

        if not first_page:
            choices.append('p')
            Console.warn('  p.\t<< Previous page')

        Console.warn('  t?.\tSet title for the conversation, eg: t1')
        Console.warn('  d?.\tDelete the conversation, eg: d1')
        Console.warn('  dd.\t!! Clear all conversations')
        Console.warn('  r.\tRefresh conversation list')

        if len(self.chatgpt.list_token_keys()) > 1:
            choices.append('k')
            Console.warn('  k.\tChoice access token')

        Console.warn('  c.\t** Start new chat')

        while True:
            choice = Prompt.ask('Your choice', choices=choices, show_choices=False)
            if choice == 'c':
                return None

            if choice == 'k':
                self.run()
                return

            if choice == 'r':
                return self.__choice_conversation(page, page_size)

            if choice == 'n':
                return self.__choice_conversation(page + 1, page_size)

            if choice == 'p':
                return self.__choice_conversation(page - 1, page_size)

            if choice == 'dd':
                self.__clear_conversations()
                continue

            if choice[0] == 't':
                self.__set_conversation_title(State(conversation_id=items[int(choice[1:]) - 1]['id']))
                return self.__choice_conversation(page, page_size)

            if choice[0] == 'd':
                self.__del_conversation(State(conversation_id=items[int(choice[1:]) - 1]['id']))
                continue

            return items[int(choice) - 1]

    def __choice_token_key(self):
        tokens = self.chatgpt.list_token_keys()

        size = len(tokens)
        if size == 1:
            return None

        choices = ['r']
        Console.info_b('Choice access token:')
        for idx, item in enumerate(tokens):
            number = str(idx + 1)
            choices.append(number)
            Console.info(f'  {number}.\t{item}')

        while True:
            choice = Prompt.ask('Your choice', choices=choices, show_choices=False)

            return tokens[int(choice) - 1]

    def __choice_model(self):
        models = self.chatgpt.list_models(token=self.token_key)

        size = len(models)
        if size == 1:
            return models[0]

        choices = ['r']
        Console.info_b('Choice model:')
        for idx, item in enumerate(models):
            number = str(idx + 1)
            choices.append(number)
            Console.info(f"  {number}.\t{item['title']} - {item['description']}")

        Console.warn('  r.\tRefresh model list')

        while True:
            choice = Prompt.ask('Your choice', choices=choices, show_choices=False)
            return self.__choice_model() if choice == 'r' else models[int(choice) - 1]

    def __copy_text(self):
        pyperclip.copy(self.state.chatgpt_prompt.prompt)
        Console.info("已将上一次返回结果复制到剪切板。")

    def __copy_code(self):
        text = self.state.chatgpt_prompt.prompt
        pattern = re.compile(r'```.*\s([\s\S]*?)\s```')
        result = re.findall(pattern, text)
        if len(result) == 0:
            Console.info("未找到代码。")
            return
        else:
            code = '\n=======================================================\n'.join(result)
            pyperclip.copy(code)
            Console.info("已将上一次生成的代码复制到剪切板。")
