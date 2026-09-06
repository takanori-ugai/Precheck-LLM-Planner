"""Message specification of the published notebooks (no LLM calls).

mode: 'single' or 'multi'; env: exact return_nlp output;
history: successfully executed actions; pc: original precondition.json.
Whitespace and grammatical errors of the original prompts are preserved.
"""

SYSTEM = "You are a life support robot."
CHAT_SYSTEM = "You are a life support robot. "
INSTRUCTION = "You need to generate a next action step for completing a household task.\n"
ALLOWED = """
Allowed actions: 
Walk, Grab, Switch on, Switch off, Open, Close, Put, Put in
Output Format: 
[WALK] <Object> (ID)
[GRAB] <Object> (ID)
[SWITCHON] <Object> (ID)
[SWITCHOFF] <Object> (ID)
[OPEN] <Object> (ID)
[CLOSE] <Object> (ID)
[PUT] <Object1> (ID) <Object2> (ID)
[PUTIN] <Object1> (ID) <Object2> (ID)

"""
CHECK = '\nIf the current status satisfies the preconditions, output "Yes"; otherwise, output "No".\n'
UNMET = 'Which the preconditions are not satisfied?\nOutput only that.'


def example_text(name, script):
    text = f"Example Task: {name}\n"
    for step, action in enumerate(script, 1):
        text += f"Step{step}: {action}\n"
    return text + "\n"


def task_text(mode, task, history):
    if mode == 'single':
        text = "\nGenerate a next action step to complete the following task and output only that.\n"
    else:
        text = "Generate a only next action step to complete the following task and output only that.\n"
    text += f"Task: {task}\n"
    for step, action in enumerate(history, 1):
        text += f"Step{step}: {action}\n"
    return text + f"Step{len(history) + 1}: "


def end_messages(mode, task, env):
    if mode == 'single':
        text = '\nOutput "End" if the following task has already completed based on the current status, otherwise output "Continue".\n'
    else:
        text = '\nIf the following task has already completed based on the current status, output "End"; otherwise, output "Continue".\n'
    return [('system', SYSTEM), ('user', env + text + f'Task: {task}\n')]


def generation_messages(mode, task, env, example, history):
    blocks = [INSTRUCTION, ALLOWED, example, env, task_text(mode, task, history)]
    if mode == 'single':
        return [('system', SYSTEM), ('user', ''.join(blocks))]
    return [('system', CHAT_SYSTEM)] + [('user', block) for block in blocks]


def bind_conditions(action, pc):
    parts = action.split(' ')
    operation = parts[0][1:-1]
    if operation not in pc:
        return None
    text = pc[operation]
    if len(parts) == 5:
        return text.replace('<Object1>', f'{parts[1]} {parts[2]}').replace('<Object2>', f'{parts[3]} {parts[4]}')
    return text.replace('<Object>', f'{parts[1]} {parts[2]}')


def check_messages(env, conditions):
    return [('user', env + CHECK + conditions)]


def unmet_messages(env, conditions, check_output):
    return [('system', CHAT_SYSTEM),
            ('user', env + CHECK + conditions),
            ('assistant', check_output),
            ('user', UNMET + conditions)]


def feedback(action, unmet_output=None):
    if unmet_output is None:
        return f"'{action}' is incorrect output format."
    return f"'{action}' can not execute, because it is not satisfied the following precondition.\n{unmet_output}"


def regeneration_messages(mode, task, env, example, history, action, reason):
    messages = generation_messages(mode, task, env, example, history)
    messages[0] = ('system', CHAT_SYSTEM)
    return messages + [('assistant', action), ('user', reason),
                       ('user', task_text(mode, task, history).replace('Generate', 'Regenerate'))]
