# Extracted from published notebooks; external globals are supplied by the notebooks.
room_list = ["bathroom", "bedroom", "kitchen", "livingroom"]

def extract_nouns(text):
    doc = nlp(text)
    nouns = [token.text for token in doc if token.pos_ == "NOUN"]
    singular_nouns = [i.singularize(noun)  for noun in nouns if i.singularize(noun) not in nouns]

    return nouns + singular_nouns

def extract_environment_knowledge(related_objects):

    g = comm.environment_graph()[1]
    nodes = g["nodes"]
    edges = g["edges"]

    # object knowledge
    objKnowledge_dic = {}
    for n in nodes:
        if n["class_name"] in related_objects:
            objKnowledge_dic[n["id"]] = {
                "states": n["states"],
                "on": None,
                "inside": None,
                "location": None,
                "hold": []
            }

    add_objId = set()
    for e in edges:
        if e["from_id"] in objKnowledge_dic.keys():
            if e["relation_type"] == "ON" and objId_dic[e["to_id"]] not in ["walk", "floor"]: # 床との関係は無視
                objKnowledge_dic[e["from_id"]]["on"] = e["to_id"]
                add_objId.add(e["to_id"])
            elif e["relation_type"] == "INSIDE":
                if objId_dic[e["to_id"]] in room_list:
                    objKnowledge_dic[e["from_id"]]["location"] = e["to_id"]
                else:
                    objKnowledge_dic[e["from_id"]]["inside"] = e["to_id"]
                    add_objId.add(e["to_id"])

        if e["to_id"] in objKnowledge_dic.keys() and e["from_id"] in objKnowledge_dic.keys():
            if e["relation_type"] == "ON" or e["relation_type"] == "INSIDE":
                objKnowledge_dic[e["to_id"]]["hold"].append(e["from_id"])
        

    # add object knowledge
    for n in nodes:
        if n["id"] in add_objId:
            objKnowledge_dic[n["id"]] = {
                "states": n["states"],
                "on": None,
                "inside": None,
                "location": None,
                "hold": []
            }
    for e in edges:
        if e["from_id"] in add_objId: 
            if e["relation_type"] == "ON" and objId_dic[e["to_id"]] not in ["walk", "floor"]: # 床との関係は無視
                objKnowledge_dic[e["from_id"]]["on"] = e["to_id"]
            elif e["relation_type"] == "INSIDE":
                if objId_dic[e["to_id"]] in room_list:
                    objKnowledge_dic[e["from_id"]]["location"] = e["to_id"]
                else:
                    objKnowledge_dic[e["from_id"]]["inside"] = e["to_id"]

        if e["to_id"] in add_objId and e["from_id"] in objKnowledge_dic.keys():
            if e["relation_type"] == "ON" or e["relation_type"] == "INSIDE":
                objKnowledge_dic[e["to_id"]]["hold"].append(e["from_id"])


    # agent knowledge
    agentKnowledge_dic = {
        "close_to": [],
        "hold_rh": None,
        "hold_lh": None,
        "location": None
    }
    for e in edges:
        if e["from_id"] == 1:
            if e["relation_type"] == "CLOSE" and e["to_id"] in objKnowledge_dic.keys():
                agentKnowledge_dic["close_to"].append(e["to_id"])
            elif e["relation_type"] == "HOLDS_RH":
                agentKnowledge_dic["hold_rh"] = e["to_id"]
            elif e["relation_type"] == "HOLDS_LH":
                agentKnowledge_dic["hold_lh"] = e["to_id"]
            elif e["relation_type"] == "INSIDE" and objId_dic[e["to_id"]] in room_list:
                agentKnowledge_dic["location"] = e["to_id"]

    return objKnowledge_dic, agentKnowledge_dic

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
