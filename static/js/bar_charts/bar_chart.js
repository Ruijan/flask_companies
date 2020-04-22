class BarChart{
    constructor(container_name, data, margin) {
        this.root = this.transformData(data)
        this.c_name = container_name
        this.margin = margin
        this.barStep = 27
        this.barPadding = 3 / this.barStep
        this.container = d3.select(container_name)
        this.width = this.container.node().getBoundingClientRect().width - this.margin.right;
        this.height = this.getHeight()
        this.container.style("height", (this.height + this.margin.bottom + this.margin.top)+"px");
    }

    getHeight(){
        return 0;
    }

    limitString(string, nbChar){
        if(string.length > nbChar){
            string = string.slice(0,nbChar - 3)
            string += "..."
        }
        return string;
    }

    transformData(data){
        return data
    }
}