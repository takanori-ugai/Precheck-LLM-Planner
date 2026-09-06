def return_nlp(a, b):

    env_prompt = "The current states in the home are as follows: \n"
    for id, knowledge in a.items():
        text = "The " + objId_dic[id] + f" ({id})"
    
        if knowledge["states"]:
            text += f" is {knowledge['states'][0]} and"
            if knowledge["on"]:
                text += f" is ON the {objId_dic[knowledge['on']]} ({knowledge['on']}) and"

            elif knowledge["inside"]:
                text += f" is INSIDE the {objId_dic[knowledge['inside']]} ({knowledge['inside']}) and"

        else:
            if knowledge["on"]:
                text += f" is ON the {objId_dic[knowledge['on']]} ({knowledge['on']}) and"

            elif knowledge["inside"]:
                text += f" is INSIDE the {objId_dic[knowledge['inside']]} ({knowledge['inside']}) and"

        if knowledge["location"]:
            text += f" and is INSIDE the {objId_dic[knowledge['location']]} ({knowledge['location']}).\n"
        else:
            text = ""

        if knowledge["hold"]:
            receptacle_type = "INSIDE" if "CONTAINERS" in objProp_dic[id] else "ON"
            text += f"{objId_dic[knowledge['hold'][0]]} ({knowledge['hold'][0]})"
            if len(knowledge["hold"]) > 1:
                for ho in knowledge["hold"][1:]:
                    text += f" and {objId_dic[ho]} ({ho})"
                text += f" are {receptacle_type} the {objId_dic[id]} ({id}).\n"
            else:
                text += f" is {receptacle_type} the {objId_dic[id]} ({id}).\n"

        env_prompt += text


    agent_prompt = f"You are INSIDE the {objId_dic[b['location']]} ({b['location']}).\n"
    if b["hold_rh"] and b["hold_lh"]:
        agent_prompt += f"You are holding the {objId_dic[b['hold_rh']]} ({b['hold_rh']}) in your right hand and the {objId_dic[b['hold_lh']]} ({b['hold_lh']}) in your left hand.\n"
    elif b["hold_rh"]:
        agent_prompt += f"You are holding the {objId_dic[b['hold_rh']]} ({b['hold_rh']}) in your right hand.\n"
    elif b["hold_lh"]:
        agent_prompt += f"You are holding the {objId_dic[b['hold_lh']]} ({b['hold_lh']}) in your left hand.\n"

    if b["close_to"]:
        agent_prompt += f"You are close to the {objId_dic[b['close_to'][0]]} ({b['close_to'][0]})"
        if len(b['close_to']) > 1:
            for c in b['close_to'][1:]:
                agent_prompt += f" and the {objId_dic[c]} ({c})"
        agent_prompt += ".\n"
    
    env_prompt += agent_prompt

    return env_prompt
