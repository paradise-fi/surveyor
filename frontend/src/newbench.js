import React, {useState} from "react";
import TextareaAutosize from 'react-textarea-autosize';
import { useForm } from "react-hook-form";
import { Button, InlineSpinbox } from "./components"
import { useHistory } from 'react-router-dom'

const LoadableTextArea = React.forwardRef((props, ref) => {
    let fileInput = React.createRef();
    let onFileChange = event => {
        let file = event.target.files[0];
        let reader = new FileReader();
        reader.onload = event => {
            props.onUpload(event.target.result);
        };
        reader.readAsText(file);
    };

    let { onUpload, ...otherProps } = props;
    return <>
        <input type="file" hidden ref={fileInput} onChange={onFileChange}/>
        <Button className="block w-full"
                type="button"
                onClick={() => fileInput.current.click() }>
            Upload from file
        </Button>
        <TextareaAutosize maxRows={20} minRows={8} ref={ref} {...otherProps}/>
    </>;
})

function FormError(props) {
    return <span className="block text-red-500">
        {props.children}
    </span>
}

export function NewBenchmark(props) {
    const { register, handleSubmit, setValue, formState } = useForm();
    let errors = formState.errors;
    const [submitting, setSubmitting] = useState(false);
    const history = useHistory();
    const onSubmit = data => {
        setSubmitting(true);
        try {
            data["tasks"] = JSON.parse(data["tasks"])
            data["memorylimit"] = data["memorylimit"] * 1024 * 1024;
        }
        catch(err) {
            setSubmitting(false);
            alert(err.message);
            return;
        }
        fetch(process.env.PUBLIC_URL + '/api/suites', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        })
            .then(response => {
                if (!response.ok) {
                    throw new Error(response.statusText);
                }
                if (response.status !== 200) {
                    return response.text().then( text => {
                        throw new Error(`Response: ${response.status}: ${text}`);
                    });
                }
                return response.json();
            })
            .then(responseJson => {
                history.push(`/suites/${responseJson["id"]}`);
            })
            .catch(e => {
                setSubmitting(false)
                alert(e.message);
            });
    };

    const defaultUpdate = { shouldValidate: true, shouldDirty: true };
    let inputStyle = `block w-full mt-1 rounded-md border-gray-300 shadow-sm
                      focus:border-indigo-300 focus:ring focus:ring-indigo-200
                      focus:ring-opacity-50`;

    return <div className="w-full p-2">
        <form onSubmit="return false;">
            <div className="w-full border-black border-b-2">
                <h1>General</h1>
                <label className="block mb-4">
                    <span className="text-gray-700">Description of the benchmarking suite</span>
                    { errors.description && errors.description.type === "required" &&
                        <FormError>Description is required</FormError>}
                    <input {...register("description", { required: true })}
                        type="text"
                        className={inputStyle}/>
                </label>
                <label className="block mb-4">
                    <span className="text-gray-700">Environment dockerfile</span>
                    { errors.dockerfile && errors.dockerfile.type === "required" &&
                        <FormError>Dockerfile is required</FormError>}
                    <LoadableTextArea
                        {...register("dockerfile", { required: true })}
                        onUpload={content => setValue("dockerfile", content, defaultUpdate)}
                        className={inputStyle}
                        defaultValue="FROM ubuntu:20.04"/>
                </label>
                <label className="block mb-4">
                    <span className="text-gray-700">Tasks JSON file</span>
                    { errors.tasks && errors.tasks.type === "required" &&
                        <FormError>Task specification is required</FormError>}
                    <LoadableTextArea
                        {...register("tasks", { required: true })}
                        onUpload={content => setValue("tasks", content, defaultUpdate)}
                        className={inputStyle}
                        defaultValue="[]"/>
                </label>
            </div>
            <div className="w-full border-black border-b-2">
                <h1>Resource limits</h1>
                <label className="block mb-4">
                    <span className="text-gray-700">CPU cores limit</span>
                    { errors.cpulimit && errors.cpulimit.type === "required" &&
                        <FormError>Number of CPU is required</FormError>}
                    <input {...register("cpulimit", { required: true, min: 0, max: 64 })}
                        defaultValue={1}
                        type="number"
                        className={inputStyle}/>
                </label>
                <label className="block mb-4">
                    <span className="text-gray-700">Wall-clock time limit in seconds</span>
                    { errors.walltimelimit &&
                        <FormError>Wall-clock time limit is required</FormError>}
                    <input {...register("walltimelimit", { required: true, min: 0})}
                        defaultValue={3600}
                        type="number"
                        className={inputStyle}/>
                </label>
                <label className="block mb-4">
                    <span className="text-gray-700">CPU time limit in seconds</span>
                    { errors.cputimelimit &&
                        <FormError>CPU time limit is required</FormError>}
                    <input {...register("cputimelimit", { required: true, min: 0})}
                        defaultValue={3600}
                        type="number"
                        className={inputStyle}/>
                </label>
                <label className="block mb-4">
                    <span className="text-gray-700">Memory limit in megabytes</span>
                    { errors.memorylimit &&
                        <FormError>Memory limit is required</FormError>}
                    <input {...register("memorylimit", { required: true, min: 1})}
                        defaultValue={1024}
                        type="number"
                        className={inputStyle}/>
                </label>
            </div>

            <Button className="w-full my-4"
                    disabled={submitting}
                    onClick={handleSubmit(onSubmit)}>
                {
                    submitting ? <InlineSpinbox/> : "Submit for evaluation"
                }
            </Button>
        </form>
    </div>
}